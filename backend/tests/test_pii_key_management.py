"""Tests de gestion des clés du PIIEncryptor (chargement, dev-file, rotation).

Couvre _load_keys : clé d'env, fichier dev existant, création du fichier dev,
clé legacy secondaire (rotation), et garde-fous du constructeur.
"""

import os

import pytest
from cryptography.fernet import Fernet

import backend.app.infrastructure.security.pii_encryptor as pii_module
from backend.app.infrastructure.security.pii_encryptor import (
    ENV_KEY_NAME,
    PIIEncryptor,
    _load_keys,
)


@pytest.fixture
def key_files(tmp_path, monkeypatch):
    """Isole les fichiers de clé dans tmp_path.

    NOTE: DEV_KEY_FILE est une constante calculée à l'import depuis __file__,
    et _load_keys reconstruit le chemin legacy depuis __file__ → on patche
    les deux.
    """
    dev_file = tmp_path / ".pii_key_main"
    monkeypatch.setattr(pii_module, "__file__", str(tmp_path / "pii_encryptor.py"))
    monkeypatch.setattr(pii_module, "DEV_KEY_FILE", str(dev_file))
    return dev_file


class TestLoadKeys:
    def test_env_key_takes_priority(self, key_files, monkeypatch):
        env_key = Fernet.generate_key().decode()
        monkeypatch.setenv(ENV_KEY_NAME, env_key)

        keys = _load_keys()

        assert keys == [env_key.encode()]
        assert not key_files.exists()  # aucun fichier créé en mode env

    def test_loads_existing_dev_file_when_no_env(self, key_files, monkeypatch):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        file_key = Fernet.generate_key()
        key_files.write_bytes(file_key + b"\n")

        keys = _load_keys()

        assert keys == [file_key]  # strip() appliqué

    def test_creates_dev_file_when_missing(self, key_files, monkeypatch):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)

        keys = _load_keys()

        assert key_files.exists()
        assert keys[0] == key_files.read_bytes().strip()
        # La clé créée est bien une clé Fernet valide
        Fernet(keys[0])

    def test_legacy_key_appended_as_secondary(self, key_files, tmp_path, monkeypatch):
        """Scénario rotation : principale (env) chiffre, legacy déchiffre."""
        old_key = Fernet.generate_key()
        new_key = Fernet.generate_key()
        # _load_keys lit .pii_key_dev à côté de __file__ (redirigé vers tmp_path)
        (tmp_path / ".pii_key_dev").write_bytes(old_key)
        monkeypatch.setenv(ENV_KEY_NAME, new_key.decode())

        encryptor = PIIEncryptor()  # charge via _load_keys

        token_old = PIIEncryptor(key=old_key).encrypt("secret-awa")
        # Déchiffrement des deux époques fonctionne
        assert encryptor.decrypt(token_old) == "secret-awa"
        assert encryptor.encrypt("nouveau") is not None


class TestEncryptorGuards:
    def test_empty_key_list_raises(self):
        with pytest.raises(ValueError, match="Aucune clé"):
            PIIEncryptor(key=[])

    def test_rotate_empty_token_returns_empty(self):
        enc = PIIEncryptor(key=Fernet.generate_key())
        assert enc.rotate("") == ""

    def test_rotate_reencrypts_with_first_key(self):
        """rotate() re-chiffre un ancien token avec la clé principale."""
        old_key, new_key = Fernet.generate_key(), Fernet.generate_key()
        enc_multi = PIIEncryptor(key=[new_key, old_key])
        old_token = PIIEncryptor(key=old_key).encrypt("données")

        rotated = enc_multi.rotate(old_token)

        assert PIIEncryptor(key=new_key).decrypt(rotated) == "données"
