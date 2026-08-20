"""
Ecahier - PostgreSQL Connection Manager
Gère le pool de connexions PostgreSQL asynchrones pour la synchronisation serveur.

Sécurité :
  - Credentials externalisés via variables d'environnement
  - Aucun fallback hardcoded — échoue explicitement si DATABASE_URL est absente
"""

import logging
import os
from typing import Any, AsyncGenerator, Optional

import asyncpg

logger = logging.getLogger(__name__)


class PostgreSQLConnectionManager:
    """Gestionnaire de connexion PostgreSQL asynchrone avec pool de connexions."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            logger.warning(
                "DATABASE_URL non définie — la synchronisation serveur sera désactivée. "
                "Définissez DATABASE_URL dans le fichier .env pour activer la sync."
            )

    async def connect(self) -> None:
        """Initialise le pool de connexions PostgreSQL."""
        if not self.db_url:
            raise RuntimeError("DATABASE_URL non configurée — impossible de se connecter.")
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=10,
                timeout=30,
                command_timeout=30,
            )
            logger.info("Pool de connexions PostgreSQL initialisé.")

    async def disconnect(self) -> None:
        """Ferme le pool de connexions PostgreSQL."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Pool de connexions PostgreSQL fermé.")

    async def get_connection(self) -> AsyncGenerator[Any, None]:
        """Fournit une connexion du pool via un générateur asynchrone."""
        if self._pool is None:
            await self.connect()
        if self._pool is not None:
            async with self._pool.acquire() as connection:
                yield connection