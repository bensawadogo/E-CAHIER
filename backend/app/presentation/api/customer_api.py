"""
Ecahier - Customer API
Endpoints REST pour la gestion des clients.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.application.dto.customer_dto import (
    CreateCustomerRequest,
    UpdateCustomerRequest,
    CustomerResponse,
    CustomerListResponse,
)
from backend.app.application.services.customer_service import CustomerService
from backend.app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customers", tags=["customers"])

_customer_service: Optional[CustomerService] = None


def set_customer_service(service: CustomerService) -> None:
    """Injecte le service client (appelé au démarrage de l'app)."""
    global _customer_service
    _customer_service = service


def get_customer_service() -> CustomerService:
    """Retourne le service client injecté."""
    if _customer_service is None:
        raise RuntimeError("CustomerService non initialisé.")
    return _customer_service


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(request: CreateCustomerRequest):
    """Crée un nouveau client."""
    service = get_customer_service()
    try:
        customer = service.create_customer(request)
        return CustomerResponse(
            id=customer.id, name=customer.name, phone=customer.phone,
            address=customer.address, notes=customer.notes, photo_path=customer.photo_path,
            total_credit=customer.total_credit, total_paid=customer.total_paid,
            balance=customer.balance, is_active=customer.is_active,
            created_at=customer.created_at, updated_at=customer.updated_at,
            sync_status=customer.sync_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=CustomerListResponse)
def list_customers(
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Liste les clients avec pagination."""
    service = get_customer_service()
    offset = (page - 1) * page_size
    if active_only:
        customers, total = service.get_active_customers(offset=offset, limit=page_size)
    else:
        customers, total = service.get_all_customers(offset=offset, limit=page_size)
    return CustomerListResponse(
        customers=[
            CustomerResponse(
                id=c.id, name=c.name, phone=c.phone, address=c.address,
                notes=c.notes, photo_path=c.photo_path,
                total_credit=c.total_credit, total_paid=c.total_paid,
                balance=c.balance, is_active=c.is_active,
                created_at=c.created_at, updated_at=c.updated_at,
                sync_status=c.sync_status,
            ) for c in customers
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/search/{query}", response_model=List[CustomerResponse])
def search_customers(query: str):
    """Recherche des clients par nom."""
    service = get_customer_service()
    customers = service.search_customers(query)
    return [
        CustomerResponse(
            id=c.id, name=c.name, phone=c.phone, address=c.address,
            notes=c.notes, photo_path=c.photo_path,
            total_credit=c.total_credit, total_paid=c.total_paid,
            balance=c.balance, is_active=c.is_active,
            created_at=c.created_at, updated_at=c.updated_at,
            sync_status=c.sync_status,
        ) for c in customers
    ]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str):
    """Récupère un client par son ID."""
    service = get_customer_service()
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")
    return CustomerResponse(
        id=customer.id, name=customer.name, phone=customer.phone,
        address=customer.address, notes=customer.notes, photo_path=customer.photo_path,
        total_credit=customer.total_credit, total_paid=customer.total_paid,
        balance=customer.balance, is_active=customer.is_active,
        created_at=customer.created_at, updated_at=customer.updated_at,
        sync_status=customer.sync_status,
    )


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: str, request: UpdateCustomerRequest):
    """Met à jour un client."""
    service = get_customer_service()
    try:
        customer = service.update_customer(customer_id, request)
        return CustomerResponse(
            id=customer.id, name=customer.name, phone=customer.phone,
            address=customer.address, notes=customer.notes, photo_path=customer.photo_path,
            total_credit=customer.total_credit, total_paid=customer.total_paid,
            balance=customer.balance, is_active=customer.is_active,
            created_at=customer.created_at, updated_at=customer.updated_at,
            sync_status=customer.sync_status,
        )
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
def delete_customer(customer_id: str):
    """Supprime un client."""
    service = get_customer_service()
    try:
        service.delete_customer(customer_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))