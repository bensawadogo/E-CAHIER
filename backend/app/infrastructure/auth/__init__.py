"""Ecahier - Auth infrastructure (JWT, password hashing)."""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)


class AuthManager:
    """Gestionnaire d'authentification simple (hash + token)."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.getenv("CAHIER_AUTH_SECRET", secrets.token_hex(32))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash un mot de passe avec SHA-256 + salt aléatoire."""
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
        return f"{salt}:{hashed}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Vérifie un mot de passe contre son hash stocké."""
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