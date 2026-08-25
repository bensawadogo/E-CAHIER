"""Tests du PostgreSQLConnectionManager avec asyncpg mocké.

Le module n'est pas encore actif (offline-first SQLite) mais doit rester
sain : mock de la frontière asyncpg, logique réelle (garde DATABASE_URL,
pool, générateur de connexion).
"""

import asyncio
import sys
import types

import pytest

from backend.app.infrastructure.database.postgresql_connection import (
    PostgreSQLConnectionManager,
)


class _AcquireContext:
    async def __aenter__(self):
        return {"fake": "connection"}

    async def __aexit__(self, *exc_info):
        return False


class FakePool:
    def __init__(self):
        self.closed = False

    def acquire(self):
        return _AcquireContext()

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_asyncpg(monkeypatch):
    """Remplace asyncpg par un double qui enregistre les appels.

    NOTE: le module cible a déjà importé asyncpg au chargement → on remplace
    l'attribut du module, pas seulement sys.modules.
    """
    module = types.ModuleType("asyncpg")
    module.calls = []
    pool_holder = {}

    async def create_pool(dsn=None, **kwargs):
        module.calls.append({"dsn": dsn, **kwargs})
        pool = FakePool()
        pool_holder["pool"] = pool
        return pool

    module.create_pool = create_pool
    module.pool_holder = pool_holder
    monkeypatch.setattr(
        "backend.app.infrastructure.database.postgresql_connection.asyncpg", module
    )
    return module


class TestWithoutDatabaseUrl:
    def test_init_without_url_warns_and_connect_raises(self, monkeypatch, caplog):
        monkeypatch.delenv("DATABASE_URL", raising=False)

        manager = PostgreSQLConnectionManager()

        assert manager.db_url is None
        assert "DATABASE_URL non définie" in caplog.text
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            asyncio.run(manager.connect())


class TestWithFakeAsyncpg:
    def test_connect_creates_pool_with_expected_params(self, monkeypatch, fake_asyncpg):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@server/db")
        manager = PostgreSQLConnectionManager()

        asyncio.run(manager.connect())

        assert fake_asyncpg.calls == [
            {
                "dsn": "postgresql://user:pass@server/db",
                "min_size": 1,
                "max_size": 10,
                "timeout": 30,
                "command_timeout": 30,
            }
        ]

    def test_get_connection_yields_pool_connection(self, monkeypatch, fake_asyncpg):
        monkeypatch.setenv("DATABASE_URL", "postgresql://s/db")
        manager = PostgreSQLConnectionManager()

        async def scenario():
            # get_connection doit auto-connecter si le pool est absent
            conns = [conn async for conn in manager.get_connection()]
            return conns

        conns = asyncio.run(scenario())
        assert conns == [{"fake": "connection"}]

    def test_disconnect_closes_pool(self, monkeypatch, fake_asyncpg):
        monkeypatch.setenv("DATABASE_URL", "postgresql://s/db")
        manager = PostgreSQLConnectionManager()
        asyncio.run(manager.connect())
        pool = fake_asyncpg.pool_holder["pool"]

        asyncio.run(manager.disconnect())

        assert pool.closed is True
        assert manager._pool is None

    def test_disconnect_without_pool_is_noop(self, monkeypatch, fake_asyncpg):
        monkeypatch.setenv("DATABASE_URL", "postgresql://s/db")
        manager = PostgreSQLConnectionManager()

        asyncio.run(manager.disconnect())  # ne doit pas lever

        assert manager._pool is None
