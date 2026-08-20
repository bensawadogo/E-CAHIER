"""
SmartLedger Africa - PII Encryptor
Chiffrement symétrique des données personnelles (PII)
telles que l'adresse, le téléphone et le chemin photo.

Utilise Fernet (AES-128-CBC + HMAC-SHA256) via la librairie `cryptography`.

Rotation de clé :
  Pendant la migration, la clé principale (CAHIER_PII_ENCRYPTION_KEY) chiffre
  les nouvelles valeurs. L'ancienne clé (fichier .pii_key_dev) reste chargée
  comme clé secondaire afin de pouvoir déchiffrer les données déjà existantes.
  Un script de migration (scripts/rotate_pii_key.py) re-chiffre ensuite toutes
  les valeurs avec la nouvelle clé et l'ancienne clé peut être retirée.
"""

import os
from typing import List, Optional, Union

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

# Nom de la variable d'environnement contenant la clé de chiffrement
ENV_KEY_NAME = "CAHIER_PII_ENCRYPTION_KEY"

# Fichier de clé en mode développement (local, non versionné)
DEV_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pii_key_main")

# Ancien fichier de clé (transition de rotation) — chargé en secondaire tant qu'il existe.
LEGACY_KEY_NAME = ".pii_key_dev"


def _load_keys() -> List[bytes]:
    """Retourne la liste des clés Fernet en vigueur (la première chiffre)."""
    keys: List[bytes] = []

    # 1) Clé principale : variable d'environnement (production / .env)
    principal = os.environ.get(ENV_KEY_NAME)
    if principal:
        keys.append(principal.encode("utf-8"))
    else:
        # Mode développement : fichier de clé persistant non versionné.
        if os.path.exists(DEV_KEY_FILE):
            with open(DEV_KEY_FILE, "rb") as f:
                keys.append(f.read().strip())
        else:
            new_key = Fernet.generate_key()
            with open(DEV_KEY_FILE, "wb") as f:
                f.write(new_key)
            keys.append(new_key)

    # 2) Clé de transition (ancienne) — chargée tant qu'elle n'a pas été retirée
    legacy_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), LEGACY_KEY_NAME)
    if os.path.exists(legacy_file):
        with open(legacy_file, "rb") as f:
            legacy = f.read().strip()
        if legacy and legacy not in keys:
            keys.append(legacy)

    if not keys:
        raise RuntimeError("Aucune clé de chiffrement PII configurée.")
    return keys


class PIIEncryptor:
    """
    Chiffre et déchiffre les données personnelles identifiables (PII).

    Utilisation :
        encryptor = PIIEncryptor()
        encrypted = encryptor.encrypt("+221 77 123 45 67")
        plain = encryptor.decrypt(encrypted)  # "+221 77 123 45 67"

    Pour la rotation, passer une liste de clés (la première chiffre) :
        encryptor = PIIEncryptor(key=[new_key, old_key])
    """

    def __init__(self, key: Optional[Union[bytes, List[bytes]]] = None):
        if key is None:
            keys = _load_keys()
        elif isinstance(key, (list, tuple)):
            keys = list(key)
        else:
            keys = [key]
        if not keys:
            raise ValueError("Aucune clé fournie au PIIEncryptor.")
        self._fernet = MultiFernet([Fernet(k) for k in keys if k])

    def encrypt(self, plaintext: str) -> str:
        """Chiffre une chaîne de caractères."""
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Déchiffre une chaîne préalablement chiffrée, ou lève ValueError."""
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Impossible de déchiffrer les données PII — token invalide.") from exc

    def rotate(self, token: str) -> str:
        """Re-chiffre un token existant avec la première clé de la liste."""
        if not token:
            return ""
        return self._fernet.rotate(token.encode("utf-8")).decode("utf-8")

    @staticmethod
    def encrypt_field(encryptor: "PIIEncryptor", value: str) -> str:
        """Méthode utilitaire statique pour chiffrer un champ."""
        return encryptor.encrypt(value)

    @staticmethod
    def decrypt_field(encryptor: "PIIEncryptor", value: str) -> str:
        """Méthode utilitaire statique pour déchiffrer un champ."""
        return encryptor.decrypt(value)
