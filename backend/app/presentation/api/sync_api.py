"""
Ecahier - Sync API
Endpoints REST pour la synchronisation offline-first.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.application.dto.sync_dto import SyncStatusResponse
from backend.app.infrastructure.sync.sync_service import SyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])

_sync_service: Optional[SyncService] = None


def set_sync_service(service: SyncService) -> None:
    global _sync_service
    _sync_service = service


def get_sync_service() -> SyncService:
    if _sync_service is None:
        raise RuntimeError("SyncService non initialisé.")
    return _sync_service


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status():
    """Retourne le statut de synchronisation."""
    service = get_sync_service()
    status_data = service.get_status()
    return SyncStatusResponse(
        is_syncing=status_data["is_syncing"],
        pending_count=status_data["pending_count"],
        server_url=status_data.get("server_url"),
        server_available=status_data.get("server_available", False),
    )


@router.post("/push")
async def push_sync():
    """Déclenche une synchronisation manuelle (push vers le serveur)."""
    service = get_sync_service()
    result = await service.sync_once()
    return {
        "message": "Synchronisation terminée.",
        "synced": result["synced"],
        "failed": result["failed"],
        "skipped": result["skipped"],
    }


@router.get("/pending")
def get_pending_operations(
    limit: int = Query(100, ge=1, le=1000),
):
    """Retourne les opérations en attente de synchronisation (limité)."""
    service = get_sync_service()
    return {
        "pending_count": service.pending_count,
        "operations": service.sync_queue.get_all()[:limit],
    }


@router.delete("/pending", status_code=status.HTTP_204_NO_CONTENT)
def clear_pending_operations():
    """Vide la file des opérations en attente."""
    service = get_sync_service()
    service.sync_queue.clear()
    logger.info("File de synchronisation vidée manuellement.")