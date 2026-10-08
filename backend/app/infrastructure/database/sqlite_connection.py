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
        self._transaction_depth = 0
        self._transaction_connection: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        """Ouvre une nouvelle connexion à la base de données SQLite.

        PRAGMA centralisés pour la durabilité (contexte Burkina Faso :
        risque de coupure secteur / arrachage de câble USB) :
          - journal_mode = WAL        : lecture concurrente + pas de lock global
          - synchronous  = FULL       : chaque écriture est flushée (aucune perte)
          - busy_timeout = 5000       : évite les SQLite_BUSY en I/O concurrent
          - foreign_keys = ON         : intégrité référentielle garantie
        """
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Nécessaire pour FastAPI (thread pool)
        )
        conn.row_factory = sqlite3.Row  # accès aux colonnes par nom -> TÂCHE 6
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA wal_autocheckpoint = 500;")
        conn.execute("PRAGMA journal_size_limit = 67108864;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        # NORMAL pouvait être utilisé sans WAL, mais FULL est requis ici.
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
    def cursor(self, conn: Optional[sqlite3.Connection] = None):
        """Fournit un curseur via un context manager avec commit/rollback automatique.
        
        Si conn est fourni, l'utilise (pour transactions explicites).
        Sinon, utilise la connexion par défaut avec auto-commit.
        """
        if conn is not None:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()
        else:
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

    @contextmanager
    def transaction(self):
        """Context manager pour une transaction explicite avec BEGIN IMMEDIATE.
        
        Utilise BEGIN IMMEDIATE pour acquérir le verrou d'écriture immédiatement,
        évitant les deadlocks en cas d'accès concurrent. Les transactions imbriquées
        sont supportées via un compteur de profondeur (seule la transaction
        la plus externe fait COMMIT/ROLLBACK réel).
        
        Usage:
            with connection_manager.transaction() as conn:
                repo1.add(entity, conn=conn)
                repo2.update(entity, conn=conn)
        """
        if self._transaction_depth == 0:
            # Transaction externe : nouvelle connexion dédiée ou réutilisation
            if self._transaction_connection is None:
                self._transaction_connection = self._connect()
            conn = self._transaction_connection
            conn.execute("BEGIN IMMEDIATE;")
        else:
            # Transaction imbriquée : réutilise la connexion existante
            conn = self._transaction_connection
            if conn is None:
                raise RuntimeError("Transaction connection lost")
            conn.execute("SAVEPOINT sp_%d;" % self._transaction_depth)
        
        self._transaction_depth += 1
        
        try:
            yield conn
            if self._transaction_depth == 1:
                conn.commit()
                logger.debug("Transaction committed")
        except Exception:
            if self._transaction_depth == 1:
                conn.rollback()
                logger.error("Transaction rolled back", exc_info=True)
            else:
                conn.execute("ROLLBACK TO SAVEPOINT sp_%d;" % (self._transaction_depth - 1))
            raise
        finally:
            self._transaction_depth -= 1
            if self._transaction_depth == 0:
                self._transaction_connection = None
