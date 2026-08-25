"""Tests d'intégration — pipeline de synchronisation offline-first.

RÉEL : SyncQueue persistée sur disque + SyncService (retry, backoff,
garde anti-concurrence, ordre FIFO).
MOCKÉ : uniquement la frontière réseau — le module `aiohttp` est remplacé
par un double scriptable (statuts HTTP programmables), comme si on
branchait un faux serveur de sync.
"""

import asyncio
import sys
import types
from typing import List, Optional, Union

import pytest


# ---------------------------------------------------------------------------
# Double aiohttp — remplace la frontière réseau
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status: int):
        self.status = status


class _ResponseContext:
    """Context manager asynchrone renvoyant la réponse (aiohttp-like)."""

    def __init__(self, coro):
        self._coro = coro

    async def __aenter__(self):
        return await self._coro

    async def __aexit__(self, *exc_info):
        return False


class FakeAiohttpServer:
    """Serveur de sync factice : scripte /health et /api/sync/push."""

    def __init__(
        self,
        health_status: int = 200,
        health_error: Optional[Exception] = None,
        push_script: Optional[List[Union[int, Exception]]] = None,
    ):
        self.calls: list[tuple[str, str]] = []
        self.push_payloads: list[dict] = []
        self.health_status = health_status
        self.health_error = health_error
        # Chaque entrée est consommée une fois ; la dernière se répète.
        self._push_script = list(push_script or [200])

    def _next_push_result(self) -> Union[int, Exception]:
        if len(self._push_script) > 1:
            return self._push_script.pop(0)
        return self._push_script[0]

    async def _request(self, method: str, url: str, payload=None):
        self.calls.append((method, url))
        if method == "GET":
            if self.health_error is not None:
                raise self.health_error
            return _FakeResponse(self.health_status)
        result = self._next_push_result()
        if isinstance(result, Exception):
            raise result
        self.push_payloads.append(payload)
        return _FakeResponse(result)

    def install(self, monkeypatch) -> None:
        server = self

        class FakeClientSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            def get(self, url, timeout=None):
                return _ResponseContext(server._request("GET", url))

            def post(self, url, json=None, timeout=None):
                return _ResponseContext(server._request("POST", url, payload=json))

        fake_module = types.ModuleType("aiohttp")
        fake_module.ClientSession = FakeClientSession
        fake_module.ClientTimeout = lambda **kwargs: None
        monkeypatch.setitem(sys.modules, "aiohttp", fake_module)


@pytest.fixture
def make_service(tmp_path):
    """Fabrique un SyncService réel avec base_delay quasi nul (tests rapides)."""
    from backend.app.infrastructure.sync.sync_queue import SyncQueue
    from backend.app.infrastructure.sync.sync_service import SyncService

    def _make(
        server_url: Optional[str] = "http://sync-server.test",
        max_retries: int = 3,
        base_delay: float = 0.001,
    ):
        queue = SyncQueue(queue_file_path=str(tmp_path / "sync_queue.json"))
        service = SyncService(
            sync_queue=queue,
            server_url=server_url,
            max_retries=max_retries,
            base_delay=base_delay,
        )
        return service, queue

    return _make


def enqueue_ops(queue, n: int) -> None:
    for i in range(n):
        queue.enqueue(
            {"entity_type": "customer", "operation": "create", "data": {"id": f"c{i}"}}
        )


pytestmark = pytest.mark.asyncio


class TestSyncSuccess:
    async def test_drains_queue_when_server_available(self, make_service, monkeypatch):
        """3 opérations en file + serveur OK → tout est poussé dans l'ordre FIFO."""
        server = FakeAiohttpServer()
        server.install(monkeypatch)

        service, queue = make_service()
        enqueue_ops(queue, 3)

        result = await service.sync_once()

        assert result == {"synced": 3, "failed": 0, "skipped": 0}
        assert queue.is_empty()
        assert [p["data"]["id"] for p in server.push_payloads] == ["c0", "c1", "c2"]
        # Le health check précède les pushes, qui ciblent /api/sync/push
        assert server.calls[0] == ("GET", "http://sync-server.test/health")
        post_urls = [url for method, url in server.calls if method == "POST"]
        assert post_urls == ["http://sync-server.test/api/sync/push"] * 3


class TestSyncOffline:
    async def test_no_server_configured_skips_everything_without_http(self, make_service):
        """server_url=None → aucune requête HTTP, opérations conservées."""
        service, queue = make_service(server_url=None)
        server = FakeAiohttpServer()
        server.install(pytest.MonkeyPatch())

        enqueue_ops(queue, 2)
        result = await service.sync_once()

        assert result == {"synced": 0, "failed": 0, "skipped": 2}
        assert server.calls == []
        assert queue.size() == 2

    async def test_server_unreachable_reports_all_skipped(self, make_service):
        """/health injoignable → skip global, aucun POST tenté."""
        service, queue = make_service()
        server = FakeAiohttpServer(health_error=ConnectionError("réseau coupé"))
        server.install(pytest.MonkeyPatch())

        enqueue_ops(queue, 2)
        result = await service.sync_once()

        assert result["skipped"] == 2
        assert not any(method == "POST" for method, _ in server.calls)
        assert queue.size() == 2


class TestSyncRetries:
    async def test_transient_failure_then_success(self, make_service):
        """1er POST échoue (500), le retry réussit → opération synchronisée."""
        service, queue = make_service(max_retries=3)
        server = FakeAiohttpServer(push_script=[500, 200])
        server.install(pytest.MonkeyPatch())

        enqueue_ops(queue, 1)
        result = await service.sync_once()

        assert result == {"synced": 1, "failed": 0, "skipped": 0}
        posts = [m for m, _ in server.calls if m == "POST"]
        assert len(posts) == 2  # 1 échec + 1 succès

    async def test_persistent_failure_exhausts_retries_and_keeps_operation(self, make_service):
        """Échec permanent → max_retries POST, échec compté, opération toujours en file."""
        service, queue = make_service(max_retries=3)
        server = FakeAiohttpServer(push_script=[500])
        server.install(pytest.MonkeyPatch())

        enqueue_ops(queue, 1)
        result = await service.sync_once()

        assert result == {"synced": 0, "failed": 1, "skipped": 0}
        posts = [m for m, _ in server.calls if m == "POST"]
        assert len(posts) == 3
        assert queue.size() == 1

    async def test_stops_on_first_failure_keeps_remaining_operations_fifo(self, make_service):
        """Op1 OK, op2 en échec → on s'arrête ; op2 et op3 restent en tête de file."""
        service, queue = make_service(max_retries=2)
        server = FakeAiohttpServer(push_script=[200, 500])
        server.install(pytest.MonkeyPatch())

        enqueue_ops(queue, 3)
        result = await service.sync_once()

        assert result == {"synced": 1, "failed": 1, "skipped": 0}
        assert queue.size() == 2
        assert queue.peek()["data"]["id"] == "c1"


class TestSyncConcurrencyAndPersistence:
    async def test_sync_not_reentrant(self, make_service):
        """Une sync déjà en cours n'est pas relancée (garde _is_syncing)."""
        service, queue = make_service()
        service._is_syncing = True

        enqueue_ops(queue, 1)
        result = await service.sync_once()

        assert result == {"synced": 0, "failed": 0, "skipped": 0}
        assert queue.size() == 1

    async def test_queue_survives_restart_then_syncs(self, make_service, tmp_path):
        """Intégration persistance : ops écrites sur disque survivent à un
        'redémarrage' (nouvelle SyncQueue/SyncService sur le même fichier)."""
        from backend.app.infrastructure.sync.sync_queue import SyncQueue
        from backend.app.infrastructure.sync.sync_service import SyncService

        path = str(tmp_path / "sync_queue.json")

        # Session 1 : enqueue puis "plantage"
        queue1 = SyncQueue(queue_file_path=path)
        enqueue_ops(queue1, 2)
        del queue1

        # Session 2 : reprise après redémarrage
        queue2 = SyncQueue(queue_file_path=path)
        service2 = SyncService(sync_queue=queue2, server_url="http://sync-server.test", max_retries=2, base_delay=0.001)
        assert service2.pending_count == 2

        server = FakeAiohttpServer()
        server.install(pytest.MonkeyPatch())
        result = await service2.sync_once()

        assert result == {"synced": 2, "failed": 0, "skipped": 0}
        assert queue2.is_empty()
