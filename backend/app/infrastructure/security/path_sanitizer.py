"""
SmartLedger Africa - Path Sanitizer
Protège contre les attaques de type path traversal
en normalisant et validant les chemins de fichiers.
"""

import os
from pathlib import Path


class PathTraversalError(ValueError):
    """Levée lorsqu'un chemin tente de sortir du répertoire autorisé."""


class PathSanitizer:
    """
    Normalise et valide les chemins de fichiers pour prévenir le path traversal.

    Utilisation :
        sanitizer = PathSanitizer(allowed_dir="/data/photos")
        safe_path = sanitizer.sanitize("customer_123.jpg")
        # Résultat : /data/photos/customer_123.jpg
    """

    def __init__(self, allowed_dir: str):
        """
        Initialise le sanitizer avec le répertoire autorisé.

        Args:
            allowed_dir: Répertoire racine dans lequel les fichiers sont autorisés.
        """
        self._allowed_dir = Path(allowed_dir).resolve()

        # Créer le répertoire s'il n'existe pas
        self._allowed_dir.mkdir(parents=True, exist_ok=True)

    def sanitize(self, user_input: str) -> str:
        """
        Nettoie et valide un chemin fourni par l'utilisateur.

        Args:
            user_input: Nom de fichier ou chemin relatif fourni par l'utilisateur.

        Returns:
            str: Chemin absolu normalisé et sécurisé.

        Raises:
            PathTraversalError: Si le chemin tente de sortir du répertoire autorisé.
            ValueError: Si le nom de fichier est vide ou invalide.
        """
        if not user_input or not user_input.strip():
            raise ValueError("Le chemin fourni ne peut pas être vide.")

        # Nettoyer les espaces et normaliser les séparateurs
        cleaned = user_input.strip().replace("\\", "/")

        # Bloquer explicitement les tentatives de path traversal
        if ".." in cleaned.split("/"):
            raise PathTraversalError(
                "Chemin refusé : '..' (path traversal) n'est pas autorisé."
            )

        # Rejeter les chemins absolus
        if cleaned.startswith("/") or cleaned.startswith("\\") or (
            len(cleaned) > 1 and cleaned[1] == ":"
        ):
            raise PathTraversalError(
                "Chemin refusé : les chemins absolus ne sont pas autorisés. "
                "Utilisez un nom de fichier ou un chemin relatif."
            )

        # Construire le chemin complet normalisé
        full_path = (self._allowed_dir / cleaned).resolve()

        # Vérifier que le chemin résolu est bien dans le répertoire autorisé
        if not str(full_path).startswith(str(self._allowed_dir)):
            raise PathTraversalError(
                f"Chemin refusé : tentative de sortie du répertoire autorisé "
                f"({self._allowed_dir})."
            )

        return str(full_path)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Nettoie un nom de fichier en supprimant les caractères dangereux.

        Args:
            filename: Nom de fichier brut.

        Returns:
            str: Nom de fichier sécurisé.
        """
        import re

        # Garder seulement les caractères sûrs
        safe = re.sub(r"[^\w\-_. ]", "", filename.strip())
        if not safe:
            raise ValueError("Le nom de fichier est invalide après nettoyage.")
        return safe
