"""
Ecahier - Sync API
Endpoints REST pour la synchronisation offline-first.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.application.dto.sync_dto import SyncStatusResponse
from backend.app.infrastructure.sync.sync_service import SyncService

from backend.app.presentation.dependencies import service_getter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])

get_sync_service = service_getter("sync_service", "SyncService")


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(service: SyncService = Depends(get_sync_service)):
    """Retourne le statut de synchronisation."""
    status_data = service.get_status()
    return SyncStatusResponse(
        is_syncing=status_data["is_syncing"],
        pending_count=status_data["pending_count"],
        server_url=status_data.get("server_url"),
        server_available=status_data.get("server_available", False),
    )


@router.post("/push")
async def push_sync(service: SyncService = Depends(get_sync_service)):
    """Déclenche une synchronisation manuelle (push vers le serveur)."""
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
    service: SyncService = Depends(get_sync_service),
):
    """Retourne les opérations en attente de synchronisation (limité)."""
    return {
        "pending_count": service.pending_count,
        "operations": service.sync_queue.get_all()[:limit],
    }


@router.delete("/pending", status_code=status.HTTP_204_NO_CONTENT)
def clear_pending_operations(service: SyncService = Depends(get_sync_service)):
    """Vide la file des opérations en attente."""
    service.sync_queue.clear()
    logger.info("File de synchronisation vidée manuellement.")