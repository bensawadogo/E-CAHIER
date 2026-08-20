"""
Ecahier - SQLite Connection Manager
Gère les connexions à la base SQLite locale (offline-first).

Optimisations pour le contexte Burkina Faso :
  - Mode WAL (Write-Ahead Logging) pour de meilleures performances
  - Clés étrangères activées pour l'intégrité des données
  - check_same_thread=False pour compatibilité avec FastAPI (thread pool)
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class SQLiteConnectionManager:
    """Gestionnaire de connexion SQLite avec mode WAL et clés étrangères activées."""

    def __init__(self, db_path: str = "data/ecahier.db"):
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        """Ouvre une nouvelle connexion à la base de données SQLite."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Nécessaire pour FastAPI (thread pool)
        )
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        # NORMAL est le meilleur compromis performances/durabilité avec WAL :
        # pas de corruption, écritures jusqu'à 3-10x plus rapides qu'en FULL,
        # idéal pour le stockage flash des téléphones bas de gamme.
        conn.execute("PRAGMA synchronous = NORMAL;")
        logger.info("Connexion SQLite ouverte: %s", self.db_path)
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Retourne la connexion SQLite active, en crée une si nécessaire."""
        if self._connection is None:
            self._connection = self._connect()
        return self._connection

    def close_connection(self) -> None:
        """Ferme la connexion SQLite active, si elle existe."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Connexion SQLite fermée: %s", self.db_path)

    @contextmanager
    def cursor(self):
        """Fournit un curseur via un context manager avec commit/rollback automatique."""
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            logger.error("Erreur transaction SQLite, rollback effectué", exc_info=True)
            raise
        finally:
            cur.close()

    @contextmanager
    def connection(self):
        """Fournit la connexion directement via un context manager (pour DDL)."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            logger.error("Erreur connexion SQLite, rollback effectué", exc_info=True)
            raise
