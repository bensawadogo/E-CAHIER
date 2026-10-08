"""
Ecahier - Sync Service
Service de synchronisation entre la base locale (SQLite) et le serveur (PostgreSQL).

Stratégie pour le contexte Burkina Faso :
  - Offline-first : toutes les opérations sont d'abord enregistrées localement
  - Sync différée : les opérations sont poussées vers le serveur quand le réseau est disponible
  - Retry avec backoff exponentiel : en cas d'échec, retry avec délai croissant
  - Détection de connectivité : vérifie la disponibilité du serveur avant sync
  - Idempotence : chaque opération porte un UUID4, le serveur déduplique sur cette clé
  - Dead-letter : les opérations échouées après max_retries sont isolées pour analyse
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

    def enqueue_operation(self, entity_type: str, operation: str, data: Dict[str, Any]) -> str:
        """
        Ajoute une opération à la file de synchronisation.

        Args:
            entity_type: Type d'entité (customer, credit, payment, transaction).
            operation: Type d'opération (create, update, delete).
            data: Données de l'entité à synchroniser.

        Returns:
            str: La clé d'idempotence (UUID4) assignée à l'opération.
        """
        return self.sync_queue.enqueue({
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
        Les opérations échouées sont déplacées vers dead-letter (ne bloquent pas la file).

        Returns:
            Dict avec les compteurs: synced, failed, dead_lettered, skipped.
        """
        if self._is_syncing:
            logger.info("Sync déjà en cours — ignoré.")
            return {"synced": 0, "failed": 0, "dead_lettered": 0, "skipped": 0}

        self._is_syncing = True
        synced = 0
        failed = 0
        dead_lettered = 0
        skipped = 0

        try:
            if not await self.check_connectivity():
                logger.info("Pas de connexion — sync reportée.")
                return {"synced": 0, "failed": 0, "dead_lettered": 0, "skipped": self.sync_queue.size()}

            while not self.sync_queue.is_empty():
                operation = self.sync_queue.peek()
                if operation is None:
                    break

                success = await self._push_operation_with_retry(operation)
                if success:
                    self.sync_queue.dequeue()
                    synced += 1
                else:
                    # Échec après tous les retries -> dead-letter, on continue
                    self.sync_queue.move_to_dead_letter(operation)
                    dead_lettered += 1
                    logger.warning(
                        "Opération %s déplacée vers dead-letter après %d échecs",
                        operation.get("idempotency_key"),
                        self.max_retries,
                    )
                    # On NE break PAS : on continue avec l'opération suivante

        finally:
            self._is_syncing = False

        logger.info(
            "Sync terminée: %d réussies, %d échouées, %d en dead-letter, %d ignorées",
            synced, failed, dead_lettered, skipped,
        )
        return {"synced": synced, "failed": failed, "dead_lettered": dead_lettered, "skipped": skipped}

    async def _push_operation_with_retry(self, operation: Dict[str, Any]) -> bool:
        """
        Pousse une opération vers le serveur avec retry et backoff exponentiel.

        Args:
            operation: L'opération à pousser (doit contenir idempotency_key).

        Returns:
            bool: True si l'opération a été synchronisée avec succès.
        """
        for attempt in range(self.max_retries):
            try:
                if await self._push_to_server(operation):
                    return True
                logger.warning(
                    "Tentative %d/%d échouée pour opération %s (clé: %s)",
                    attempt + 1, self.max_retries,
                    operation.get("entity_type"),
                    operation.get("idempotency_key"),
                )
            except Exception as e:
                logger.error("Erreur sync tentative %d: %s", attempt + 1, e)

            delay = self.base_delay * (2 ** attempt)
            await asyncio.sleep(delay)

        return False

    async def _push_to_server(self, operation: Dict[str, Any]) -> bool:
        """
        Pousse une opération vers le serveur via HTTP avec la clé d'idempotence.

        Args:
            operation: L'opération à pousser (avec idempotency_key).

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
                    json=operation,  # Inclut idempotency_key
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info("Opération syncée: %s (clé: %s)", operation.get("entity_type"), operation.get("idempotency_key"))
                        return True
                    elif response.status == 409:
                        # Conflit d'idempotence : l'opération existe déjà côté serveur
                        logger.info("Opération déjà traitée côté serveur (idempotence): %s", operation.get("idempotency_key"))
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