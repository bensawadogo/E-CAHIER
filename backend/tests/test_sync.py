"""Unit tests for the sync layer (SyncQueue and SyncService)."""

import json

import pytest


# ---------------------------------------------------------------------------
# SyncQueue
# ---------------------------------------------------------------------------
class TestSyncQueue:
    def test_new_queue_is_empty(self, sync_queue):
        assert sync_queue.is_empty()
        assert sync_queue.size() == 0
        assert sync_queue.peek() is None
        assert sync_queue.dequeue() is None

    def test_enqueue_dequeue_fifo(self, sync_queue):
        sync_queue.enqueue({"entity_type": "customer", "operation": "create", "data": {}})
        sync_queue.enqueue({"entity_type": "credit", "operation": "create", "data": {}})
        assert sync_queue.size() == 2

        first = sync_queue.dequeue()
        assert first["entity_type"] == "customer"
        second = sync_queue.dequeue()
        assert second["entity_type"] == "credit"
        assert sync_queue.is_empty()

    def test_peek_does_not_remove(self, sync_queue):
        op = {"entity_type": "payment", "operation": "create", "data": {}}
        sync_queue.enqueue(op)
        assert sync_queue.peek() == op
        assert sync_queue.size() == 1

    def test_get_all_returns_copy(self, sync_queue):
        sync_queue.enqueue({"entity_type": "customer", "operation": "create", "data": {}})
        ops = sync_queue.get_all()
        ops.append({"evil": True})
        assert sync_queue.size() == 1

    def test_clear(self, sync_queue):
        sync_queue.enqueue({"entity_type": "customer", "operation": "create", "data": {}})
        sync_queue.clear()
        assert sync_queue.is_empty()
        assert sync_queue.size() == 0

    def test_persistence_across_instances(self, tmp_path):
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        path = str(tmp_path / "sync_queue.json")
        q1 = SyncQueue(queue_file_path=path)
        q1.enqueue({"entity_type": "credit", "operation": "create", "data": {"amount": "5000"}})

        q2 = SyncQueue(queue_file_path=path)
        assert q2.size() == 1
        peeked = q2.peek()
        assert peeked is not None
        assert peeked["entity_type"] == "credit"
        dequeued = q2.dequeue()
        assert dequeued is not None
        assert dequeued["data"]["amount"] == "5000"
        assert q2.is_empty()

    def test_corrupted_json_file_resets_queue(self, tmp_path):
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        path = tmp_path / "sync_queue.json"
        path.write_text("{not valid json", encoding="utf-8")
        q = SyncQueue(queue_file_path=str(path))
        assert q.is_empty()
        assert q.size() == 0

    def test_clear_removes_file(self, tmp_path):
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        path = tmp_path / "sync_queue.json"
        q = SyncQueue(queue_file_path=str(path))
        q.enqueue({"entity_type": "customer", "operation": "create", "data": {}})
        assert path.exists()
        q.clear()
        assert not path.exists()

    def test_dequeue_empty_returns_none_and_preserves(self, tmp_path):
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        path = tmp_path / "sync_queue.json"
        q = SyncQueue(queue_file_path=str(path))
        assert q.dequeue() is None


# ---------------------------------------------------------------------------
# SyncService
# ---------------------------------------------------------------------------
class TestSyncService:
    def test_pending_count(self, sync_service):
        assert sync_service.pending_count == 0
        sync_service.enqueue_operation("customer", "create", {"name": "Awa"})
        assert sync_service.pending_count == 1

    def test_enqueue_operation_format(self, sync_service, sync_queue):
        sync_service.enqueue_operation("payment", "update", {"id": "p1"})
        op = sync_queue.peek()
        assert op == {
            "entity_type": "payment",
            "operation": "update",
            "data": {"id": "p1"},
        }

    def test_is_syncing_initial_false(self, sync_service):
        assert sync_service.is_syncing is False

    def test_check_connectivity_no_server(self, sync_service):
        import asyncio

        assert asyncio.run(sync_service.check_connectivity()) is False

    def test_get_status(self, sync_service):
        sync_service.enqueue_operation("customer", "create", {"name": "Awa"})
        status = sync_service.get_status()
        assert status["is_syncing"] is False
        assert status["pending_count"] == 1
        assert status["server_url"] is None
        assert status["server_available"] is False

    @pytest.mark.asyncio
    async def test_sync_once_without_server_skips(self, sync_service):
        sync_service.enqueue_operation("customer", "create", {"name": "Awa"})
        result = await sync_service.sync_once()
        assert result["synced"] == 0
        assert result["failed"] == 0
        # Offline mode: all pending are reported as skipped.
        assert result["skipped"] == 1
        # The queue still holds the operation.
        assert sync_service.pending_count == 1

    @pytest.mark.asyncio
    async def test_sync_once_reentrancy(self, sync_service, monkeypatch):
        async def fake_check():
            return True

        monkeypatch.setattr(sync_service, "check_connectivity", fake_check)
        sync_service._is_syncing = True  # simulate an in-progress sync
        result = await sync_service.sync_once()
        assert result == {"synced": 0, "failed": 0, "skipped": 0}

    @pytest.mark.asyncio
    async def test_sync_once_success_dequeues(self, sync_service, monkeypatch):
        async def fake_check():
            return True

        async def fake_push(operation):
            return True

        monkeypatch.setattr(sync_service, "check_connectivity", fake_check)
        monkeypatch.setattr(sync_service, "_push_operation_with_retry", fake_push)

        sync_service.enqueue_operation("customer", "create", {"name": "Awa"})
        sync_service.enqueue_operation("credit", "create", {"amount": "100"})

        result = await sync_service.sync_once()
        assert result["synced"] == 2
        assert result["failed"] == 0
        assert sync_service.pending_count == 0

    @pytest.mark.asyncio
    async def test_sync_once_failure_stops(self, sync_service, monkeypatch):
        async def fake_check():
            return True

        async def fake_push(operation):
            return False

        monkeypatch.setattr(sync_service, "check_connectivity", fake_check)
        monkeypatch.setattr(sync_service, "_push_operation_with_retry", fake_push)

        sync_service.enqueue_operation("customer", "create", {"name": "Awa"})
        sync_service.enqueue_operation("credit", "create", {"amount": "100"})

        result = await sync_service.sync_once()
        assert result["synced"] == 0
        assert result["failed"] == 1
        # First operation stays in the queue because push failed.
        assert sync_service.pending_count == 2

    @pytest.mark.asyncio
    async def test_push_operation_with_retry_exhausts_retries(
        self, sync_service, monkeypatch
    ):
        # Configure a tiny service so retries don't sleep long.
        from backend.app.infrastructure.sync.sync_service import SyncService
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        svc = SyncService(
            sync_queue=SyncQueue(),
            server_url=None,
            max_retries=3,
            base_delay=0.0,
        )
        calls = []

        async def fake_push(operation):
            calls.append(operation)
            return False

        async def fake_sleep(_):
            return None

        monkeypatch.setattr(svc, "_push_to_server", fake_push)
        monkeypatch.setattr("asyncio.sleep", fake_sleep)

        result = await svc._push_operation_with_retry({"entity_type": "x"})
        # _push_to_server returns False, so it should retry up to max_retries.
        assert len(calls) == 3
        assert result is False

    @pytest.mark.asyncio
    async def test_push_operation_with_retry_succeeds_on_first(self, sync_service, monkeypatch):
        from backend.app.infrastructure.sync.sync_service import SyncService
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        svc = SyncService(
            sync_queue=SyncQueue(),
            server_url="http://example.invalid",
            max_retries=3,
            base_delay=0.0,
        )
        calls = []

        async def fake_push(operation):
            calls.append(operation)
            return True

        async def fake_sleep(_):
            return None

        monkeypatch.setattr(svc, "_push_to_server", fake_push)
        monkeypatch.setattr("asyncio.sleep", fake_sleep)

        result = await svc._push_operation_with_retry({"entity_type": "x"})
        assert result is True
        assert len(calls) == 1

    def test_sync_service_config_defaults(self):
        from backend.app.infrastructure.sync.sync_service import SyncService
        from backend.app.infrastructure.sync.sync_queue import SyncQueue

        svc = SyncService(sync_queue=SyncQueue())
        assert svc.max_retries == 3
        assert svc.base_delay == 1.0
        assert svc.server_url is None

