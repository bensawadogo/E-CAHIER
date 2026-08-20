"""
SmartLedger Africa - PII Encryptor
Chiffrement symétrique des données personnelles (PII)
telles que l'adresse, le téléphone et le chemin photo.
Utilise Fernet (AES-128-CBC + HMAC-SHA256) via la librairie `cryptography`.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


# Nom de la variable d'environnement contenant la clé de chiffrement
ENV_KEY_NAME = "CAHIER_PII_ENCRYPTION_KEY"


def _get_or_create_key() -> bytes:
    """Récupère la clé depuis l'environnement ou en génère une en mode développement."""
    key = os.environ.get(ENV_KEY_NAME)
    if key:
        return key.encode("utf-8")
    # Mode développement seulement — générer une clé persistante dans un fichier
    key_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".pii_key_dev"
    )
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read().strip()
    # Générer une nouvelle clé
    new_key = Fernet.generate_key()
    with open(key_file, "wb") as f:
        f.write(new_key)
    return new_key


class PIIEncryptor:
    """
    Chiffre et déchiffre les données personnelles identifiables (PII).

    Utilisation :
        encryptor = PIIEncryptor()
        encrypted = encryptor.encrypt("+221 77 123 45 67")
        plain = encryptor.decrypt(encrypted)  # "+221 77 123 45 67"
    """

    def __init__(self, key: Optional[bytes] = None):
        self._fernet = Fernet(key if key else _get_or_create_key())

    def encrypt(self, plaintext: str) -> str:
        """
        Chiffre une chaîne de caractères.
        Retourne le texte chiffré en base64 (str).
        Retourne une chaîne vide si l'entrée est vide.
        """
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """
        Déchiffre une chaîne de caractères préalablement chiffrée.
        Retourne le texte clair.
        Retourne une chaîne vide si l'entrée est vide.
        Lève ValueError si le token est invalide.
        """
        if not ciphertext or ciphertext == "":
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Impossible de déchiffrer les données PII — token invalide.") from exc

    @staticmethod
    def encrypt_field(encryptor: "PIIEncryptor", value: str) -> str:
        """Méthode utilitaire statique pour chiffrer un champ."""
        return encryptor.encrypt(value)

    @staticmethod
    def decrypt_field(encryptor: "PIIEncryptor", value: str) -> str:
        """Méthode utilitaire statique pour déchiffrer un champ."""
        return encryptor.decrypt(value)
