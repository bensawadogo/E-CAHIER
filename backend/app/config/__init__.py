"""
Ecahier - Configuration
Charge les variables d'environnement et configure l'application.
"""

import logging
import os
from logging.config import dictConfig

from dotenv import load_dotenv

# Charger le fichier .env s'il existe
load_dotenv()


class Settings:
    """Configuration globale de l'application."""

    # Application
    APP_NAME: str = "Ecahier API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("CAHIER_DEBUG", "false").lower() == "true"

    # Base de données locale (SQLite) — offline-first
    SQLITE_PATH: str = os.getenv("CAHIER_SQLITE_PATH", "data/ecahier.db")

    # Base de données serveur (PostgreSQL) — sync optionnelle
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Sécurité
    PII_ENCRYPTION_KEY: str = os.getenv("CAHIER_PII_ENCRYPTION_KEY", "")
    AUTH_SECRET: str = os.getenv("CAHIER_AUTH_SECRET", "")

    # Stockage
    PHOTOS_DIR: str = os.getenv("CAHIER_PHOTOS_DIR", "data/photos")
    STORAGE_DIR: str = os.getenv("CAHIER_STORAGE_DIR", "data/storage")

    # Sync
    SYNC_QUEUE_PATH: str = os.getenv("CAHIER_SYNC_QUEUE_PATH", "data/sync_queue.json")
    SERVER_URL: str = os.getenv("CAHIER_SERVER_URL", "")
    SYNC_MAX_RETRIES: int = int(os.getenv("CAHIER_SYNC_MAX_RETRIES", "3"))
    SYNC_BASE_DELAY: float = float(os.getenv("CAHIER_SYNC_BASE_DELAY", "1.0"))

    # OCR
    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "tesseract")

    # API
    API_HOST: str = os.getenv("CAHIER_API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("CAHIER_API_PORT", "8000"))

    # Frontend static serving
    SERVE_FRONTEND: bool = os.getenv("CAHIER_SERVE_FRONTEND", "false").lower() == "true"


settings = Settings()


def setup_logging() -> None:
    """Configure le logging structuré."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
    })


__all__ = ["Settings", "settings", "setup_logging"]