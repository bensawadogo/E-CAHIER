"""
Ecahier - Transaction API
Endpoints REST pour la lecture du journal des opérations.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.application.dto.transaction_dto import (
    TransactionResponse,
    TransactionListResponse,
)
from backend.app.application.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transactions", tags=["transactions"])

_transaction_service: Optional[TransactionService] = None


def set_transaction_service(service: TransactionService) -> None:
    """Injecte le service des transactions (appelé au démarrage de l'app)."""
    global _transaction_service
    _transaction_service = service


def get_transaction_service() -> TransactionService:
    """Retourne le service des transactions injecté."""
    if _transaction_service is None:
        raise RuntimeError("TransactionService non initialisé.")
    return _transaction_service


def _to_response(t) -> TransactionResponse:
    return TransactionResponse(
        id=t.id,
        customer_id=t.customer_id,
        credit_id=t.credit_id,
        payment_id=t.payment_id,
        type=t.type,
        amount=t.amount,
        balance_after=t.balance_after,
        description=t.description,
        created_at=t.created_at,
        sync_status=t.sync_status,
    )


@router.get("/", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Liste toutes les transactions (journal global) avec pagination."""
    service = get_transaction_service()
    offset = (page - 1) * page_size
    transactions, total = service.get_all_transactions(offset=offset, limit=page_size)
    return TransactionListResponse(
        transactions=[_to_response(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customer/{customer_id}", response_model=List[TransactionResponse])
def get_customer_transactions(customer_id: str):
    """Retourne l'historique complet des opérations d'un client."""
    service = get_transaction_service()
    transactions = service.get_customer_transactions(customer_id)
    return [_to_response(t) for t in transactions]
