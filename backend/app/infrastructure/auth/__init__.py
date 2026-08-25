"""Ecahier - Auth infrastructure (JWT, password hashing)."""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)


_PBKDF2_ITERATIONS = 210000
_PBKDF2_ALGORITHM_TAG = "pbkdf2_sha256"


class AuthManager:
    """Gestionnaire d'authentification simple (hash + token).

    Hash de mot de passe au format ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``
    (PBKDF2-HMAC-SHA256, 210000 itérations par défaut). Les anciens hash
    ``sha256+salt`` (format ``<salt_hex>:<hash_hex>``) restent vérifiables ;
    utiliser :meth:`needs_rehash` puis :meth:`hash_password` pour migrer un
    compte lors d'une connexion réussie.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.getenv("CAHIER_AUTH_SECRET", secrets.token_hex(32))

    @staticmethod
    def hash_password(password: str, iterations: int = _PBKDF2_ITERATIONS) -> str:
        """Hash un mot de passe avec PBKDF2-HMAC-SHA256 + salt aléatoire."""
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"{_PBKDF2_ALGORITHM_TAG}${iterations}${salt.hex()}${derived.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Vérifie un mot de passe contre son hash stocké.

        Détecte le format par préfixe : nouveau format PBKDF2 ou ancien
        format ``<salt>:<hash>`` (SHA-256 simple, conservé pour compat).
        """
        if stored_hash.startswith(f"{_PBKDF2_ALGORITHM_TAG}$"):
            return AuthManager._verify_pbkdf2(password, stored_hash)
        return AuthManager._verify_legacy_sha256(password, stored_hash)

    @staticmethod
    def needs_rehash(stored_hash: str) -> bool:
        """True si le hash est dans l'ancien format et doit être re-hashé.

        À appeler après une vérification réussie d'un ancien hash afin de le
        remplacer par le nouveau format PBKDF2 (migration à la volée).
        """
        return not stored_hash.startswith(f"{_PBKDF2_ALGORITHM_TAG}$")

    @staticmethod
    def _verify_pbkdf2(password: str, stored_hash: str) -> bool:
        try:
            _, iter_str, salt_hex, hash_hex = stored_hash.split("$")
            iterations = int(iter_str)
            expected = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                iterations,
            )
            return hmac.compare_digest(expected, bytes.fromhex(hash_hex))
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _verify_legacy_sha256(password: str, stored_hash: str) -> bool:
        try:
            salt, hashed = stored_hash.split(":")
            test_hash = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
            return hmac.compare_digest(hashed, test_hash)
        except (ValueError, AttributeError):
            return False

    def generate_token(self, user_id: str) -> str:
        """Génère un token d'authentification simple."""
        return f"{user_id}:{secrets.token_hex(32)}"

    def verify_token(self, token: str) -> Optional[str]:
        """Vérifie un token et retourne l'ID utilisateur, ou None si invalide."""
        try:
            user_id, _ = token.split(":", 1)
            return user_id
        except (ValueError, AttributeError):
            return None


__all__ = ["AuthManager"]