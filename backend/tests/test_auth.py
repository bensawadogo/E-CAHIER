"""Tests d'authentification pour TÂCHE 5.

Vérifie que le middleware d'auth bloque les requêtes sans token valide.
NOTE: ``client`` (fixture) envoie par défaut le header Authorization ;
``noauth_client`` n'en envoie pas — c'est lui qu'on utilise ici.
"""

import hashlib
import secrets

from backend.app.infrastructure.auth import AuthManager


class TestPasswordHashing:
    """Hash de mot de passe PBKDF2-HMAC-SHA256 (+ compat ancien format)."""

    def test_hash_format_is_pbkdf2(self):
        stored = AuthManager.hash_password("s3cret!")
        parts = stored.split("$")
        assert len(parts) == 4
        tag, iterations, salt_hex, hash_hex = parts
        assert tag == "pbkdf2_sha256"
        assert int(iterations) == 210000
        bytes.fromhex(salt_hex)
        bytes.fromhex(hash_hex)

    def test_hash_differs_on_each_call(self):
        a = AuthManager.hash_password("same-password")
        b = AuthManager.hash_password("same-password")
        assert a != b

    def test_verify_ok(self):
        stored = AuthManager.hash_password("mon-mot-de-passe")
        assert AuthManager.verify_password("mon-mot-de-passe", stored) is True

    def test_verify_rejects_wrong_password(self):
        stored = AuthManager.hash_password("mon-mot-de-passe")
        assert AuthManager.verify_password("mauvais", stored) is False

    def test_verify_rejects_malformed_hash(self):
        assert AuthManager.verify_password("x", "") is False
        assert AuthManager.verify_password("x", "not-a-hash") is False
        assert AuthManager.verify_password("x", "pbkdf2_sha256$abc$00$00") is False

    def test_legacy_sha256_salt_hash_still_verified(self):
        # Ancien format : <salt_hex>:<sha256(salt+password)>
        salt = secrets.token_hex(16)
        legacy_hash = hashlib.sha256(f"{salt}old-pass".encode("utf-8")).hexdigest()
        legacy_stored = f"{salt}:{legacy_hash}"
        assert AuthManager.verify_password("old-pass", legacy_stored) is True
        assert AuthManager.verify_password("wrong", legacy_stored) is False

    def test_needs_rehash_flags_legacy_only(self):
        salt = secrets.token_hex(16)
        legacy_stored = f"{salt}:{hashlib.sha256(f'{salt}p'.encode()).hexdigest()}"
        assert AuthManager.needs_rehash(legacy_stored) is True
        assert AuthManager.needs_rehash(AuthManager.hash_password("p")) is False

    def test_legacy_can_be_migrated_to_pbkdf2(self):
        salt = secrets.token_hex(16)
        legacy_stored = f"{salt}:old-pass-hash"
        if AuthManager.verify_password("real-pass", legacy_stored.replace("old-pass-hash",
            hashlib.sha256(f"{salt}real-pass".encode()).hexdigest())):
            migrated = AuthManager.hash_password("real-pass")
            assert AuthManager.verify_password("real-pass", migrated) is True
            assert AuthManager.needs_rehash(migrated) is False


class TestAuth:
    def test_unauthorized_without_token(self, noauth_client):
        """Toute route /api/* sans token → 401."""
        r = noauth_client.get("/api/customers/")
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_unauthorized_with_bad_token(self, noauth_client):
        """Un token invalide → 401."""
        r = noauth_client.get(
            "/api/customers/",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    def test_authorized_with_token(self, client):
        """Avec le bon token (header par défaut du fixture) → 200."""
        r = client.get("/api/customers/")
        assert r.status_code == 200

    def test_health_endpoint_without_token(self, noauth_client):
        """Les routes hors /api/* (ex: /health) restent accessibles sans token."""
        r = noauth_client.get("/health")
        assert r.status_code == 200
