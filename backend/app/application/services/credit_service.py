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
from backend.app.domain.repositories.payment_repository import PaymentRepository
from backend.app.domain.repositories.transaction_repository import TransactionRepository
from backend.app.application.dto.credit_dto import (
    CreateCreditRequest,
    UpdateCreditRequest,
)
from backend.app.application.services.errors import ConflictError
from backend.app.application.services.ledger import sync_credit_status, sync_customer_totals
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager

logger = logging.getLogger(__name__)


class CreditService:
    """Service applicatif pour la gestion des crédits."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        transaction_repository: Optional[TransactionRepository] = None,
        connection_manager: Optional[SQLiteConnectionManager] = None,
        payment_repository: Optional[PaymentRepository] = None,
    ):
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.transaction_repository = transaction_repository
        self.connection_manager = connection_manager
        # Sans lui, modifier/supprimer un crédit ne recalcule pas les soldes.
        self.payment_repository = payment_repository

    def create_credit(self, request: CreateCreditRequest) -> Credit:
        """Crée un nouveau crédit pour un client. Tout se passe dans une transaction atomique."""
        def _do_create(conn):
            # Vérifier que le client existe
            customer = self.customer_repository.get_by_id(request.customer_id, conn=conn)
            if not customer:
                raise ValueError(f"Client introuvable: {request.customer_id}")

            # Idempotence : un renvoi après coupure ne doit pas doubler la dette.
            if request.id:
                existing = self.credit_repository.get_by_id(request.id, conn=conn)
                if existing:
                    if existing.customer_id != request.customer_id:
                        raise ValueError(f"Identifiant déjà utilisé: {request.id}")
                    return existing

            # Date d'échéance par défaut : 30 jours
            due_date = request.due_date or datetime.now(timezone.utc) + timedelta(days=30)

            extra = {"id": request.id} if request.id else {}
            credit = Credit(
                customer_id=request.customer_id,
                amount=request.amount,
                description=request.description,
                due_date=due_date,
                **extra,
            )
            saved = self.credit_repository.add(credit, conn=conn)

            # Mettre à jour le total_credit du client
            customer.total_credit += request.amount
            self.customer_repository.update(customer, conn=conn)

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
                self.transaction_repository.add(transaction, conn=conn)

            logger.info("Crédit créé: %s pour client %s (montant: %s)", saved.id, request.customer_id, request.amount)
            return saved

        if self.connection_manager:
            with self.connection_manager.transaction() as conn:
                return _do_create(conn)
        else:
            # Fallback sans transaction (pour tests avec fake repositories)
            return _do_create(None)

    def get_credit(self, credit_id: str, conn=None) -> Optional[Credit]:
        """Récupère un crédit par son ID."""
        return self.credit_repository.get_by_id(credit_id, conn=conn)

    def get_customer_credits(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Credit]:
        """Récupère tous les crédits d'un client (paginé)."""
        return self.credit_repository.get_by_customer(
            customer_id, offset=offset, limit=limit, conn=conn
        )

    def get_all_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
        updated_since: Optional[str] = None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère tous les crédits (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        extra = {"updated_since": updated_since} if updated_since else {}
        credits = self.credit_repository.get_all(
            offset=offset, limit=limit, conn=conn, **extra
        )
        total = self.credit_repository.count_all(conn=conn, **extra)
        return credits, total

    def get_pending_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère les crédits non payés (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        credits = self.credit_repository.get_pending(offset=offset, limit=limit, conn=conn)
        total = self.credit_repository.count_pending(conn=conn)
        return credits, total

    def get_overdue_credits(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> Tuple[List[Credit], int]:
        """
        Récupère les crédits en retard (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        credits = self.credit_repository.get_overdue(offset=offset, limit=limit, conn=conn)
        total = self.credit_repository.count_overdue(conn=conn)
        return credits, total

    def _atomic(self, work, conn=None):
        """Exécute ``work(conn)`` en une transaction (ou dans celle fournie)."""
        if conn is not None:
            return work(conn)
        if self.connection_manager:
            with self.connection_manager.transaction() as tx:
                return work(tx)
        return work(None)

    def update_credit(self, credit_id: str, request: UpdateCreditRequest, conn=None) -> Credit:
        """Met à jour un crédit et remet statut et totaux du client d'aplomb."""
        def _do(conn):
            credit = self.credit_repository.get_by_id(credit_id, conn=conn)
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
            elif self.payment_repository is not None:
                # Le montant a pu changer : le statut suit les paiements.
                sync_credit_status(credit, self.payment_repository, conn=conn)

            updated = self.credit_repository.update(credit, conn=conn)
            if self.payment_repository is not None:
                sync_customer_totals(
                    credit.customer_id, self.customer_repository,
                    self.credit_repository, self.payment_repository, conn=conn,
                )
            logger.info("Crédit mis à jour: %s", credit_id)
            return updated

        return self._atomic(_do, conn)

    def delete_credit(self, credit_id: str, conn=None) -> None:
        """Supprime un crédit SANS paiement ; sinon refuse (annulez-le plutôt)."""
        def _do(conn):
            credit = self.credit_repository.get_by_id(credit_id, conn=conn)
            if not credit:
                raise ValueError(f"Aucun crédit trouvé avec l'ID {credit_id}.")
            if self.payment_repository is not None and self.payment_repository.get_by_credit(
                credit_id, limit=1, conn=conn
            ):
                raise ConflictError(
                    "Ce crédit a déjà des paiements : annulez-le (statut « cancelled ») "
                    "au lieu de le supprimer."
                )
            self.credit_repository.delete(credit_id, conn=conn)
            if self.payment_repository is not None:
                sync_customer_totals(
                    credit.customer_id, self.customer_repository,
                    self.credit_repository, self.payment_repository, conn=conn,
                )
            logger.info("Crédit supprimé: %s", credit_id)

        self._atomic(_do, conn)
