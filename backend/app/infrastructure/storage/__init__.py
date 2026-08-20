"""Ecahier - Storage infrastructure (file storage for photos, receipts)."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FileStorage:
    """Gestionnaire de stockage de fichiers (photos, reçus) avec compression."""

    def __init__(self, base_dir: str = "data/storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename: str, content: bytes) -> str:
        """Sauvegarde un fichier et retourne son chemin relatif."""
        safe_name = Path(filename).name  # Évite le path traversal
        file_path = self.base_dir / safe_name
        file_path.write_bytes(content)
        logger.info("Fichier sauvegardé: %s", file_path)
        return str(file_path.relative_to(self.base_dir.parent))

    def get_file_path(self, filename: str) -> str:
        """Retourne le chemin absolu d'un fichier."""
        safe_name = Path(filename).name
        return str(self.base_dir / safe_name)

    def file_exists(self, filename: str) -> bool:
        """Vérifie si un fichier existe."""
        safe_name = Path(filename).name
        return (self.base_dir / safe_name).exists()

    def delete_file(self, filename: str) -> bool:
        """Supprime un fichier. Retourne True si supprimé, False sinon."""
        safe_name = Path(filename).name
        file_path = self.base_dir / safe_name
        if file_path.exists():
            file_path.unlink()
            logger.info("Fichier supprimé: %s", file_path)
            return True
        return False


__all__ = ["FileStorage"]