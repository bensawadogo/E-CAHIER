"""
Ecahier - Credit API
Endpoints REST pour la gestion des crédits.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.application.dto.credit_dto import (
    CreateCreditRequest,
    UpdateCreditRequest,
    CreditResponse,
    CreditListResponse,
)
from backend.app.application.services.credit_service import CreditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/credits", tags=["credits"])

_credit_service: Optional[CreditService] = None


def set_credit_service(service: CreditService) -> None:
    global _credit_service
    _credit_service = service


def get_credit_service() -> CreditService:
    if _credit_service is None:
        raise RuntimeError("CreditService non initialisé.")
    return _credit_service


def _to_response(credit) -> CreditResponse:
    return CreditResponse(
        id=credit.id, customer_id=credit.customer_id, amount=credit.amount,
        description=credit.description, due_date=credit.due_date,
        status=credit.status, is_overdue=credit.is_overdue,
        created_at=credit.created_at, updated_at=credit.updated_at,
        sync_status=credit.sync_status,
    )


@router.post("/", response_model=CreditResponse, status_code=status.HTTP_201_CREATED)
def create_credit(request: CreateCreditRequest):
    """Crée un nouveau crédit."""
    service = get_credit_service()
    try:
        return _to_response(service.create_credit(request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=CreditListResponse)
def list_credits(
    pending_only: bool = Query(False),
    overdue_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Liste les crédits avec pagination et filtres."""
    service = get_credit_service()
    offset = (page - 1) * page_size
    if overdue_only:
        credits, total = service.get_overdue_credits(offset=offset, limit=page_size)
    elif pending_only:
        credits, total = service.get_pending_credits(offset=offset, limit=page_size)
    else:
        credits, total = service.get_all_credits(offset=offset, limit=page_size)
    return CreditListResponse(
        credits=[_to_response(c) for c in credits],
        total=total, page=page, page_size=page_size,
    )


@router.get("/customer/{customer_id}", response_model=List[CreditResponse])
def get_customer_credits(customer_id: str):
    """Récupère tous les crédits d'un client."""
    service = get_credit_service()
    return [_to_response(c) for c in service.get_customer_credits(customer_id)]


@router.get("/{credit_id}", response_model=CreditResponse)
def get_credit(credit_id: str):
    """Récupère un crédit par son ID."""
    service = get_credit_service()
    credit = service.get_credit(credit_id)
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crédit introuvable.")
    return _to_response(credit)


@router.put("/{credit_id}", response_model=CreditResponse)
def update_credit(credit_id: str, request: UpdateCreditRequest):
    """Met à jour un crédit."""
    service = get_credit_service()
    try:
        return _to_response(service.update_credit(credit_id, request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{credit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credit(credit_id: str):
    """Supprime un crédit."""
    service = get_credit_service()
    try:
        service.delete_credit(credit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))