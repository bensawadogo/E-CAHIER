"""
Ecahier - Customer API
Endpoints REST pour la gestion des clients.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.application.dto.customer_dto import (
    CreateCustomerRequest,
    UpdateCustomerRequest,
    CustomerResponse,
    CustomerListResponse,
)
from backend.app.application.services.customer_service import CustomerService
from backend.app.config import settings

from backend.app.presentation.dependencies import service_getter, updated_since_param

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customers", tags=["customers"])

get_customer_service = service_getter("customer_service", "CustomerService")


def _to_response(customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id, name=customer.name, phone=customer.phone,
        address=customer.address, notes=customer.notes, photo_path=customer.photo_path,
        total_credit=customer.total_credit, total_paid=customer.total_paid,
        balance=customer.balance, is_active=customer.is_active,
        created_at=customer.created_at, updated_at=customer.updated_at,
        sync_status=customer.sync_status,
    )


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    request: CreateCustomerRequest,
    service: CustomerService = Depends(get_customer_service),
):
    """Crée un nouveau client."""
    try:
        return _to_response(service.create_customer(request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=CustomerListResponse)
def list_customers(
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    updated_since: Optional[str] = Depends(updated_since_param),
    service: CustomerService = Depends(get_customer_service),
):
    """Liste les clients avec pagination.

    ``updated_since`` : lecture incrémentale (prioritaire sur ``active_only``).
    """
    offset = (page - 1) * page_size
    if active_only and not updated_since:
        customers, total = service.get_active_customers(offset=offset, limit=page_size)
    else:
        customers, total = service.get_all_customers(
            offset=offset, limit=page_size, updated_since=updated_since
        )
    return CustomerListResponse(
        customers=[_to_response(c) for c in customers],
        total=total, page=page, page_size=page_size,
    )


@router.get("/search/{query}", response_model=List[CustomerResponse])
def search_customers(
    query: str,
    service: CustomerService = Depends(get_customer_service),
):
    """Recherche des clients par nom."""
    customers = service.search_customers(query)
    return [_to_response(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
):
    """Récupère un client par son ID."""
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")
    return _to_response(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str, request: UpdateCustomerRequest,
    service: CustomerService = Depends(get_customer_service),
):
    """Met à jour un client."""
    try:
        return _to_response(service.update_customer(customer_id, request))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/_echo", include_in_schema=False)
def echo_payload(payload: dict):
    """Endpoint de test pour la compression : renvoie le payload reçu.

    Garde-fou : désactivé hors mode debug (404 en production).
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return payload


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
):
    """Supprime un client."""
    try:
        service.delete_customer(customer_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))