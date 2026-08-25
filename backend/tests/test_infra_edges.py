"""Tests des cas limites infrastructure : rollback SQLite, sync queue corrompue."""

import pytest

from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager
from backend.app.infrastructure.sync.sync_queue import SyncQueue


class TestSqliteRollback:
    def test_connection_context_rollback_on_exception(self, tmp_path):
        """Une exception dans le CM `connection()` → rollback, écriture annulée."""
        manager = SQLiteConnectionManager(db_path=":memory:")
        conn = manager.get_connection()
        conn.execute("CREATE TABLE t (v TEXT)")

        with pytest.raises(RuntimeError):
            with manager.connection() as c:
                c.execute("INSERT INTO t VALUES ('perdu')")
                raise RuntimeError("boom")

        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
        manager.close_connection()

    def test_cursor_context_commit_on_success(self, tmp_path):
        manager = SQLiteConnectionManager(db_path=":memory:")
        conn = manager.get_connection()
        conn.execute("CREATE TABLE t (v TEXT)")

        with manager.cursor() as cur:
            cur.execute("INSERT INTO t VALUES ('gardé')")

        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        manager.close_connection()

    def test_cursor_context_rollback_on_exception(self, tmp_path):
        manager = SQLiteConnectionManager(db_path=":memory:")
        conn = manager.get_connection()
        conn.execute("CREATE TABLE t (v TEXT)")

        with pytest.raises(RuntimeError):
            with manager.cursor() as cur:
                cur.execute("INSERT INTO t VALUES ('perdu')")
                raise RuntimeError("boom")

        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
        manager.close_connection()


class TestSyncQueueEdgeCases:
    def test_corrupt_json_resets_queue(self, tmp_path):
        """Fichier de queue corrompu → file vide, pas d'exception."""
        path = tmp_path / "queue.json"
        path.write_text("{invalid json !!", encoding="utf-8")

        queue = SyncQueue(queue_file_path=str(path))

        assert queue.size() == 0
        assert queue.is_empty()

    def test_enqueue_survives_save_failure(self, tmp_path, caplog):
        """Échec d'écriture disque → erreur loguée, opération gardée en mémoire."""
        # Un répertoire à la place du fichier → open() en écriture échoue
        target_dir = tmp_path / "queue.json"
        target_dir.mkdir()

        queue = SyncQueue(queue_file_path=str(target_dir))
        queue.enqueue({"entity_type": "customer", "operation": "create", "data": {}})

        assert queue.size() == 1  # l'opération reste en mémoire malgré l'échec I/O

    def test_load_nonexistent_file_starts_empty(self, tmp_path):
        queue = SyncQueue(queue_file_path=str(tmp_path / "absent.json"))
        assert queue.is_empty()
