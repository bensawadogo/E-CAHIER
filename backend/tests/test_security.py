"""Unit tests for the security layer (PIIEncryptor and PathSanitizer)."""

import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.infrastructure.security.pii_encryptor import PIIEncryptor
from backend.app.infrastructure.security.path_sanitizer import (
    PathSanitizer,
    PathTraversalError,
)


# ---------------------------------------------------------------------------
# PIIEncryptor
# ---------------------------------------------------------------------------
class TestPIIEncryptor:
    def _make(self):
        return PIIEncryptor(key=Fernet.generate_key())

    def test_roundtrip(self):
        enc = self._make()
        plain = "+226 70 12 34 56"
        token = enc.encrypt(plain)
        assert token != plain
        assert enc.decrypt(token) == plain

    def test_roundtrip_unicode(self):
        enc = self._make()
        plain = "Awa Ouédraogo — Ouagadougou"
        assert enc.decrypt(enc.encrypt(plain)) == plain

    def test_empty_plaintext_returns_empty(self):
        enc = self._make()
        assert enc.encrypt("") == ""

    def test_empty_ciphertext_returns_empty(self):
        enc = self._make()
        assert enc.decrypt("") == ""

    def test_ciphertext_differs_across_calls(self):
        enc = self._make()
        # Fernet is randomized; two encryptions of the same text differ.
        assert enc.encrypt("hello") != enc.encrypt("hello")

    def test_different_keys_produce_different_ciphertext(self):
        enc1 = self._make()
        enc2 = self._make()
        assert enc1.encrypt("secret") != enc2.encrypt("secret")

    def test_decrypt_invalid_token_raises_valueerror(self):
        enc = self._make()
        with pytest.raises(ValueError):
            enc.decrypt("not-a-valid-fernet-token")

    def test_decrypt_garbage_raises_valueerror(self):
        enc = self._make()
        with pytest.raises(ValueError):
            enc.decrypt("!!!")

    def test_static_helpers(self):
        enc = self._make()
        token = PIIEncryptor.encrypt_field(enc, "field-value")
        assert PIIEncryptor.decrypt_field(enc, token) == "field-value"

    def test_roundtrip_with_explicit_key(self):
        key = Fernet.generate_key()
        enc = PIIEncryptor(key=key)
        assert enc.decrypt(enc.encrypt("data")) == "data"


# ---------------------------------------------------------------------------
# PathSanitizer
# ---------------------------------------------------------------------------
class TestPathSanitizer:
    @pytest.fixture
    def allowed_dir(self, tmp_path):
        d = tmp_path / "photos"
        d.mkdir()
        return d

    @pytest.fixture
    def sanitizer(self, allowed_dir):
        return PathSanitizer(allowed_dir=str(allowed_dir))

    def test_simple_filename(self, sanitizer, allowed_dir):
        result = sanitizer.sanitize("photo.jpg")
        assert Path(result) == (allowed_dir / "photo.jpg").resolve()

    def test_relative_subdir(self, sanitizer, allowed_dir):
        result = sanitizer.sanitize("customer-1/photo.jpg")
        assert Path(result) == (allowed_dir / "customer-1" / "photo.jpg").resolve()

    def test_windows_separators_normalized(self, sanitizer, allowed_dir):
        result = sanitizer.sanitize("customer-1\\photo.jpg")
        assert Path(result) == (allowed_dir / "customer-1" / "photo.jpg").resolve()

    def test_whitespace_stripped(self, sanitizer, allowed_dir):
        result = sanitizer.sanitize("  photo.jpg  ")
        assert Path(result) == (allowed_dir / "photo.jpg").resolve()

    def test_empty_input_rejected(self, sanitizer):
        with pytest.raises(ValueError):
            sanitizer.sanitize("")

    def test_whitespace_only_rejected(self, sanitizer):
        with pytest.raises(ValueError):
            sanitizer.sanitize("   ")

    @pytest.mark.parametrize("malicious", ["../secret.txt", "a/../../secret.txt"])
    def test_path_traversal_rejected(self, sanitizer, malicious):
        with pytest.raises(PathTraversalError):
            sanitizer.sanitize(malicious)

    @pytest.mark.parametrize("absolute", ["/etc/passwd", "\\windows\\system32", "C:/secret"])
    def test_absolute_path_rejected(self, sanitizer, absolute):
        with pytest.raises(PathTraversalError):
            sanitizer.sanitize(absolute)

    def test_escapes_allowed_dir_rejected(self, tmp_path):
        other = tmp_path / "other"
        other.mkdir()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        s = PathSanitizer(allowed_dir=str(allowed))
        # Build a path that resolves outside via symlink-free traversal is
        # blocked because ".." segments are rejected. Confirm absolute escape
        # is also rejected.
        with pytest.raises(PathTraversalError):
            s.sanitize(str(other / "x.png"))

    def test_sanitize_filename_strips_dangerous_chars(self):
        assert PathSanitizer.sanitize_filename("my photo!.jpg") == "my photo.jpg"
        # Dots are allowed; slashes are removed, so traversal input is neutralised.
        assert PathSanitizer.sanitize_filename("../../evil") == "....evil"

    def test_sanitize_filename_raises_on_invalid(self):
        with pytest.raises(ValueError):
            PathSanitizer.sanitize_filename("!!!")

    def test_sanitize_filename_empty_raises(self):
        with pytest.raises(ValueError):
            PathSanitizer.sanitize_filename("")


# ---------------------------------------------------------------------------
# Integration: SQLiteCustomerRepository PII + path handling
# ---------------------------------------------------------------------------
class TestRepositorySecurity:
    def test_customer_pii_is_encrypted_at_rest(self, in_memory_db, customer_repo):
        from backend.app.domain.entities.customer import Customer

        c = Customer(name="Awa", phone="+226 70 00 00 00", address="Ouaga 2000")
        customer_repo.add(c)

        with in_memory_db.cursor() as cur:
            cur.execute(
                "SELECT phone, address FROM customers WHERE id = ?", (c.id,)
            )
            row = cur.fetchone()

        # Stored PII must not appear in plaintext.
        assert row[0] != "+226 70 00 00 00"
        assert row[1] != "Ouaga 2000"
        assert "+226" not in row[0]

        # Read back via repository → decrypted.
        loaded = customer_repo.get_by_id(c.id)
        assert loaded.phone == "+226 70 00 00 00"
        assert loaded.address == "Ouaga 2000"

    def test_validate_and_save_photo_returns_safe_path(
        self, in_memory_db, pii_encryptor, tmp_path
    ):
        from backend.app.infrastructure.database.repositories.customer_repository_impl import (
            SQLiteCustomerRepository,
        )
        from backend.app.infrastructure.security.path_sanitizer import PathSanitizer

        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        repo = SQLiteCustomerRepository(
            in_memory_db, pii_encryptor, PathSanitizer(str(photos_dir))
        )
        result = repo.validate_and_save_photo("cust-1", "photo.jpg")
        assert Path(result) == (photos_dir / "cust-1" / "photo.jpg").resolve()

    def test_validate_and_save_photo_neutralizes_traversal(
        self, in_memory_db, pii_encryptor, tmp_path
    ):
        from backend.app.infrastructure.database.repositories.customer_repository_impl import (
            SQLiteCustomerRepository,
        )
        from backend.app.infrastructure.security.path_sanitizer import PathSanitizer

        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        repo = SQLiteCustomerRepository(
            in_memory_db, pii_encryptor, PathSanitizer(str(photos_dir))
        )
        # `sanitize_filename` strips the slashes, so the traversal input is
        # neutralised into a safe filename that stays inside the photos dir.
        result = repo.validate_and_save_photo("cust-1", "../../../etc/passwd")
        result_path = Path(result)
        assert str(result_path).startswith(str(photos_dir.resolve()))

