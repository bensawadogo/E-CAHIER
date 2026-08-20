"""
Ecahier - Sync Service
Service de synchronisation entre la base locale (SQLite) et le serveur (PostgreSQL).

Stratégie pour le contexte Burkina Faso :
  - Offline-first : toutes les opérations sont d'abord enregistrées localement
  - Sync différée : les opérations sont poussées vers le serveur quand le réseau est disponible
  - Retry avec backoff exponentiel : en cas d'échec, retry avec délai croissant
  - Détection de connectivité : vérifie la disponibilité du serveur avant sync
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.app.infrastructure.sync.sync_queue import SyncQueue

logger = logging.getLogger(__name__)


class SyncService:
    """Service de synchronisation offline-first avec retry et backoff."""

    def __init__(
        self,
        sync_queue: SyncQueue,
        server_url: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.sync_queue = sync_queue
        self.server_url = server_url
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._is_syncing = False

    @property
    def is_syncing(self) -> bool:
        """Indique si une synchronisation est en cours."""
        return self._is_syncing

    @property
    def pending_count(self) -> int:
        """Nombre d'opérations en attente de synchronisation."""
        return self.sync_queue.size()

    def enqueue_operation(self, entity_type: str, operation: str, data: Dict[str, Any]) -> None:
        """
        Ajoute une opération à la file de synchronisation.

        Args:
            entity_type: Type d'entité (customer, credit, payment, transaction).
            operation: Type d'opération (create, update, delete).
            data: Données de l'entité à synchroniser.
        """
        self.sync_queue.enqueue({
            "entity_type": entity_type,
            "operation": operation,
            "data": data,
        })

    async def check_connectivity(self) -> bool:
        """Vérifie si le serveur est accessible."""
        if not self.server_url:
            return False
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception:
            logger.warning("Serveur inaccessible: %s", self.server_url)
            return False

    async def sync_once(self) -> Dict[str, int]:
        """
        Tente de synchroniser toutes les opérations en file une seule fois.

        Returns:
            Dict avec les compteurs: synced, failed, skipped.
        """
        if self._is_syncing:
            logger.info("Sync déjà en cours — ignoré.")
            return {"synced": 0, "failed": 0, "skipped": 0}

        self._is_syncing = True
        synced = 0
        failed = 0
        skipped = 0

        try:
            if not await self.check_connectivity():
                logger.info("Pas de connexion — sync reportée.")
                return {"synced": 0, "failed": 0, "skipped": self.sync_queue.size()}

            while not self.sync_queue.is_empty():
                operation = self.sync_queue.peek()
                if operation is None:
                    break

                success = await self._push_operation_with_retry(operation)
                if success:
                    self.sync_queue.dequeue()
                    synced += 1
                else:
                    failed += 1
                    break  # Arrêter sur échec pour éviter de tout perdre

        finally:
            self._is_syncing = False

        logger.info("Sync terminée: %d réussies, %d échouées, %d ignorées", synced, failed, skipped)
        return {"synced": synced, "failed": failed, "skipped": skipped}

    async def _push_operation_with_retry(self, operation: Dict[str, Any]) -> bool:
        """
        Pousse une opération vers le serveur avec retry et backoff exponentiel.

        Args:
            operation: L'opération à pousser.

        Returns:
            bool: True si l'opération a été synchronisée avec succès.
        """
        for attempt in range(self.max_retries):
            try:
                if await self._push_to_server(operation):
                    return True
                logger.warning(
                    "Tentative %d/%d échouée pour opération %s",
                    attempt + 1, self.max_retries, operation.get("entity_type"),
                )
            except Exception as e:
                logger.error("Erreur sync tentative %d: %s", attempt + 1, e)

            # Backoff exponentiel: 1s, 2s, 4s, 8s...
            delay = self.base_delay * (2 ** attempt)
            await asyncio.sleep(delay)

        return False

    async def _push_to_server(self, operation: Dict[str, Any]) -> bool:
        """
        Pousse une opération vers le serveur via HTTP.

        Args:
            operation: L'opération à pousser.

        Returns:
            bool: True si le serveur a confirmé la réception.
        """
        if not self.server_url:
            return False

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/sync/push",
                    json=operation,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info("Opération syncée: %s", operation.get("entity_type"))
                        return True
                    else:
                        logger.error("Erreur serveur sync: status %d", response.status)
                        return False
        except Exception as e:
            logger.error("Erreur push sync: %s", e)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut de synchronisation."""
        return {
            "is_syncing": self._is_syncing,
            "pending_count": self.pending_count,
            "server_url": self.server_url,
            "server_available": self.server_url is not None,
        }