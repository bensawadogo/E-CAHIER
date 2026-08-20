"""TÂCHE 4 — Durabilité SQLite face aux coupures de courant.

Vérifie que TOUTE connexion ouverte par ``SQLiteConnectionManager`` applique
systématiquement les PRAGMA de durabilité :
  - journal_mode = WAL
  - synchronous  = FULL   (ne pas perdre les dernières écritures en cas de coupure)
  - busy_timeout = 5000
  - foreign_keys = ON
"""

import sqlite3

import pytest

from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager

PRAGMA_READONLY = {
    "journal_mode": "journal_mode",
    "foreign_keys": "foreign_keys",
    "busy_timeout": "busy_timeout",
}
# synchronous n'est pas lisible via PRAGMA ; on vérifie par son effet appliqué.


def _pragma_values(conn: sqlite3.Connection) -> dict:
    return {
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0],
        "busy_timeout": conn.execute("PRAGMA busy_timeout").fetchone()[0],
    }


class TestSQLiteConnectionDurability:
    def test_pragmas_applied_on_file_connection(self, tmp_path):
        db = str(tmp_path / "durability.db")
        manager = SQLiteConnectionManager(db_path=db)
        conn = manager.get_connection()
        try:
            values = _pragma_values(conn)
            assert values["journal_mode"] == "wal", values
            assert values["foreign_keys"] == 1, values
            assert values["busy_timeout"] == 5000, values
            # synchronous=FULL est le réglage attendu (vérifié via journal WAL du fichier)
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2, \
                "synchronous doit être à 2 (FULL)"
        finally:
            manager.close_connection()

    def test_row_factory_enabled_for_named_access(self, tmp_path):
        # Symétrie avec la TÂCHE 6 : la connexion expose des lignes par nom.
        manager = SQLiteConnectionManager(db_path=str(tmp_path / "row.db"))
        conn = manager.get_connection()
        try:
            assert conn.row_factory is sqlite3.Row, "row_factory doit être sqlite3.Row"
        finally:
            manager.close_connection()

    def test_repeated_get_connection_returns_single_reusable_conn(self, tmp_path):
        manager = SQLiteConnectionManager(db_path=str(tmp_path / "single.db"))
        a = manager.get_connection()
        b = manager.get_connection()
        assert a is b
        manager.close_connection()
        assert manager._connection is None