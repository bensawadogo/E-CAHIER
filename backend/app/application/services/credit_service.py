"""
Ecahier - Credit Service
Orchestre les use cases liés aux crédits (création, suivi, statut).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.repositories.credit_repository import CreditRepository
from backend.app.domain.repositories.customer_repository import CustomerRepository
from backend.app.domain.repositories.transaction_repository import TransactionRepository
from backend.app.application.dto.credit_dto import (
    CreateCreditRequest,
    UpdateCreditRequest,
)

logger = logging.getLogger(__name__)


class CreditService:
    """Service applicatif pour la gestion des crédits."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        transaction_repository: Optional[TransactionRepository] = None,
    ):
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.transaction_repository = transaction_repository

    def create_credit(self, request: CreateCreditRequest) -> Credit:
        """Crée un nouveau crédit pour un client."""
        # Vérifier que le client existe
        customer = self.customer_repository.get_by_id(request.customer_id)
        if not customer:
            raise ValueError(f"Client introuvable: {request.customer_id}")

        # Date d'échéance par défaut : 30 jours
        due_date = request.due_date or datetime.now(timezone.utc) + timedelta(days=30)

        credit = Credit(
            customer_id=request.customer_id,
            amount=request.amount,
            description=request.description,
            due_date=due_date,
        )
        saved = self.credit_repository.add(credit)

        # Mettre à jour le total_credit du client
        customer.total_credit += request.amount
        self.customer_repository.update(customer)

        # Enregistrer la transaction dans le journal (si le repository est fourni)
        if self.transaction_repository is not None:
            transaction = Transaction(
                customer_id=request.customer_id,
                credit_id=saved.id,
                type="credit",
                amount=request.amount,
                balance_after=customer.balance,
                description=request.description or "Crédit octroyé",
            )
            self.transaction_repository.add(transaction)

        logger.info("Crédit créé: %s pour client %s (montant: %s)", saved.id, request.customer_id, request.amount)
        return saved

    def get_credit(self, credit_id: str) -> Optional[Credit]:
        """Récupère un crédit par son ID."""
        return self.credit_repository.get_by_id(credit_id)

    def get_customer_credits(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Credit]:
        """Récupère tous les crédits d'un client (paginé)."""
        return self.credit_repository.get_by_customer(
            customer_id, offset=offset, limit=limit
        )

    def get_all_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère tous les crédits (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        credits = self.credit_repository.get_all(offset=offset, limit=limit)
        total = self.credit_repository.count_all()
        return credits, total

    def get_pending_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère les crédits non payés (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        credits = self.credit_repository.get_pending(offset=offset, limit=limit)
        total = self.credit_repository.count_pending()
        return credits, total

    def get_overdue_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère les crédits en retard (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        credits = self.credit_repository.get_overdue(offset=offset, limit=limit)
        total = self.credit_repository.count_overdue()
        return credits, total

    def update_credit(self, credit_id: str, request: UpdateCreditRequest) -> Credit:
        """Met à jour un crédit existant."""
        credit = self.credit_repository.get_by_id(credit_id)
        if not credit:
            raise ValueError(f"Crédit introuvable: {credit_id}")

        if request.amount is not None:
            credit.amount = request.amount
        if request.description is not None:
            credit.description = request.description
        if request.due_date is not None:
            credit.due_date = request.due_date
        if request.status is not None:
            credit.status = request.status

        updated = self.credit_repository.update(credit)
        logger.info("Crédit mis à jour: %s", credit_id)
        return updated

    def delete_credit(self, credit_id: str) -> None:
        """Supprime un crédit."""
        self.credit_repository.delete(credit_id)
        logger.info("Crédit supprimé: %s", credit_id)