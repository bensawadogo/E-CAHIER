"""
Ecahier - Payment API
Endpoints REST pour la gestion des paiements.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.application.dto.payment_dto import (
    RecordPaymentRequest,
    UpdatePaymentRequest,
    PaymentResponse,
    PaymentListResponse,
)
from backend.app.application.services.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

_payment_service: Optional[PaymentService] = None


def set_payment_service(service: PaymentService) -> None:
    global _payment_service
    _payment_service = service


def get_payment_service() -> PaymentService:
    if _payment_service is None:
        raise RuntimeError("PaymentService non initialisé.")
    return _payment_service


def _to_response(payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id, customer_id=payment.customer_id, credit_id=payment.credit_id,
        amount=payment.amount, method=payment.method, reference=payment.reference,
        note=payment.note, payment_date=payment.payment_date,
        created_at=payment.created_at, updated_at=payment.updated_at,
        sync_status=payment.sync_status,
    )


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment(request: RecordPaymentRequest):
    """Enregistre un nouveau paiement."""
    service = get_payment_service()
    try:
        return _to_response(service.record_payment(request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=PaymentListResponse)
def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Liste les paiements avec pagination."""
    service = get_payment_service()
    offset = (page - 1) * page_size
    payments, total = service.get_all_payments(offset=offset, limit=page_size)
    return PaymentListResponse(
        payments=[_to_response(p) for p in payments],
        total=total, page=page, page_size=page_size,
    )


@router.get("/customer/{customer_id}", response_model=List[PaymentResponse])
def get_customer_payments(customer_id: str):
    """Récupère tous les paiements d'un client."""
    service = get_payment_service()
    return [_to_response(p) for p in service.get_customer_payments(customer_id)]


@router.get("/credit/{credit_id}", response_model=List[PaymentResponse])
def get_credit_payments(credit_id: str):
    """Récupère tous les paiements liés à un crédit."""
    service = get_payment_service()
    return [_to_response(p) for p in service.get_credit_payments(credit_id)]


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str):
    """Récupère un paiement par son ID."""
    service = get_payment_service()
    payment = service.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paiement introuvable.")
    return _to_response(payment)


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: str, request: UpdatePaymentRequest):
    """Met à jour un paiement."""
    service = get_payment_service()
    try:
        return _to_response(service.update_payment(payment_id, request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(payment_id: str):
    """Supprime un paiement."""
    service = get_payment_service()
    try:
        service.delete_payment(payment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))