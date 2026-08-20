"""
Ecahier - Customer Service
Orchestre les use cases liés aux clients (CRUD + recherche).
"""

import logging
from typing import List, Optional, Tuple

from backend.app.domain.entities.customer import Customer
from backend.app.domain.repositories.customer_repository import CustomerRepository
from backend.app.application.dto.customer_dto import (
    CreateCustomerRequest,
    UpdateCustomerRequest,
)

logger = logging.getLogger(__name__)


class CustomerService:
    """Service applicatif pour la gestion des clients."""

    def __init__(self, customer_repository: CustomerRepository):
        self.customer_repository = customer_repository

    def create_customer(self, request: CreateCustomerRequest) -> Customer:
        """Crée un nouveau client."""
        customer = Customer(
            name=request.name,
            phone=request.phone,
            address=request.address,
            notes=request.notes,
            photo_path=request.photo_path,
        )
        saved = self.customer_repository.add(customer)
        logger.info("Client créé: %s (%s)", saved.name, saved.id)
        return saved

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Récupère un client par son ID."""
        return self.customer_repository.get_by_id(customer_id)

    def get_all_customers(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List[Customer], int]:
        """
        Récupère tous les clients (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        customers = self.customer_repository.get_all(offset=offset, limit=limit)
        total = self.customer_repository.count_all()
        return customers, total

    def get_active_customers(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List[Customer], int]:
        """
        Récupère les clients actifs uniquement (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        customers = self.customer_repository.get_active(offset=offset, limit=limit)
        total = self.customer_repository.count_active()
        return customers, total

    def update_customer(self, customer_id: str, request: UpdateCustomerRequest) -> Customer:
        """Met à jour un client existant."""
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Client introuvable: {customer_id}")

        if request.name is not None:
            customer.name = request.name
        if request.phone is not None:
            customer.phone = request.phone
        if request.address is not None:
            customer.address = request.address
        if request.notes is not None:
            customer.notes = request.notes
        if request.photo_path is not None:
            customer.photo_path = request.photo_path
        if request.is_active is not None:
            customer.is_active = request.is_active

        updated = self.customer_repository.update(customer)
        logger.info("Client mis à jour: %s", customer_id)
        return updated

    def attach_photo(self, customer_id: str, photo_path: str) -> Customer:
        """Attache une photo à un client (chemin d'accès web)."""
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Client introuvable: {customer_id}")
        customer.photo_path = photo_path
        updated = self.customer_repository.update(customer)
        logger.info("Photo attachée au client %s: %s", customer_id, photo_path)
        return updated

    def delete_customer(self, customer_id: str) -> None:
        """Supprime un client."""
        self.customer_repository.delete(customer_id)
        logger.info("Client supprimé: %s", customer_id)

    def search_customers(
        self,
        query: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Customer]:
        """Recherche des clients par nom (paginé)."""
        return self.customer_repository.search_by_name(
            query, offset=offset, limit=limit
        )
