"""Ecahier - Sync DTOs (Data Transfer Objects)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SyncPushRequest(BaseModel):
    """DTO pour pousser des opérations vers le serveur."""
    operations: List[Dict[str, Any]] = Field(..., description="Opérations à synchroniser")


class SyncPullResponse(BaseModel):
    """DTO pour la réponse de pull de synchronisation."""
    customers: List[Dict[str, Any]] = Field(default_factory=list)
    credits: List[Dict[str, Any]] = Field(default_factory=list)
    payments: List[Dict[str, Any]] = Field(default_factory=list)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    last_sync: Optional[str] = Field(None, description="Timestamp de la dernière sync")


class SyncStatusResponse(BaseModel):
    """DTO pour le statut de synchronisation."""
    is_syncing: bool
    pending_count: int
    server_url: Optional[str] = None
    server_available: bool = False
    last_sync: Optional[str] = None