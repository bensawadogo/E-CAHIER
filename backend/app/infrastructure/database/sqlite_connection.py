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
import threading
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
        # Connexion dédiée aux transactions, réutilisée (ouvrir une connexion
        # + 7 PRAGMA à chaque requête coûte cher sur un petit VPS).
        self._tx_conn_cache: Optional[sqlite3.Connection] = None
        # Une seule transaction à la fois, TOUS threads confondus : FastAPI
        # exécute les routes synchrones dans un pool de threads. Sans ce
        # verrou, un 2e thread « imbriquait » sa transaction dans celle du 1er
        # (commit/rollback mélangés). RLock : le MÊME thread peut imbriquer.
        self._tx_lock = threading.RLock()
        # La connexion par défaut est partagée par tous les threads de FastAPI.
        # Un objet sqlite3.Connection ne supporte pas l'usage simultané de
        # plusieurs curseurs (InterfaceError / SystemError) : on le protège.
        self._conn_lock = threading.RLock()

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
        if self._tx_conn_cache:
            self._tx_conn_cache.close()
            self._tx_conn_cache = None

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
            with self._conn_lock:
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
        with self._conn_lock:
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
        with self._tx_lock:
            if self._transaction_depth == 0:
                # Transaction externe : connexion dédiée (créée une seule fois).
                if self._tx_conn_cache is None:
                    self._tx_conn_cache = self._connect()
                self._transaction_connection = self._tx_conn_cache
                conn = self._transaction_connection
                conn.execute("BEGIN IMMEDIATE;")
            else:
                # Transaction imbriquée (même thread) : même connexion.
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
                else:
                    conn.execute("RELEASE SAVEPOINT sp_%d;" % (self._transaction_depth - 1))
            except Exception:
                if self._transaction_depth == 1:
                    conn.rollback()
                    logger.error("Transaction rolled back", exc_info=True)
                else:
                    conn.execute("ROLLBACK TO SAVEPOINT sp_%d;" % (self._transaction_depth - 1))
                    conn.execute("RELEASE SAVEPOINT sp_%d;" % (self._transaction_depth - 1))
                raise
            finally:
                self._transaction_depth -= 1
                if self._transaction_depth == 0:
                    self._transaction_connection = None
