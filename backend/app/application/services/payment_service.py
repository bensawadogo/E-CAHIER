"""
Ecahier - Payment Service
Orchestre les use cases liés aux paiements (enregistrement, suivi).
"""

import logging
from decimal import Decimal
from typing import List, Optional, Tuple

from backend.app.domain.entities.payment import Payment
from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.repositories.payment_repository import PaymentRepository
from backend.app.domain.repositories.credit_repository import CreditRepository
from backend.app.domain.repositories.customer_repository import CustomerRepository
from backend.app.domain.repositories.transaction_repository import TransactionRepository
from backend.app.application.dto.payment_dto import (
    RecordPaymentRequest,
    UpdatePaymentRequest,
)
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager

logger = logging.getLogger(__name__)


class PaymentService:
    """Service applicatif pour la gestion des paiements."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        transaction_repository: TransactionRepository,
        connection_manager: Optional[SQLiteConnectionManager] = None,
    ):
        self.payment_repository = payment_repository
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.transaction_repository = transaction_repository
        self.connection_manager = connection_manager

    def record_payment(self, request: RecordPaymentRequest) -> Payment:
        """
        Enregistre un paiement et met à jour les entités liées (crédit, client, transaction).
        Tout se passe dans une transaction atomique (BEGIN IMMEDIATE).
        """
        def _do_record(conn):
            # Vérifier que le client existe
            customer = self.customer_repository.get_by_id(request.customer_id, conn=conn)
            if not customer:
                raise ValueError(f"Client introuvable: {request.customer_id}")

            # Vérifier que le crédit existe
            credit = self.credit_repository.get_by_id(request.credit_id, conn=conn)
            if not credit:
                raise ValueError(f"Crédit introuvable: {request.credit_id}")

            # Créer le paiement
            payment = Payment(
                customer_id=request.customer_id,
                credit_id=request.credit_id,
                amount=request.amount,
                method=request.method,
                reference=request.reference,
                note=request.note,
            )
            saved_payment = self.payment_repository.add(payment, conn=conn)

            # Mettre à jour le total_paid du client
            customer.total_paid += request.amount
            self.customer_repository.update(customer, conn=conn)

            # Mettre à jour le statut du crédit (SUM SQL — évite de charger
            # tous les paiements en mémoire, important sur téléphone bas de gamme)
            total_paid_for_credit = self.payment_repository.total_paid_for_credit(credit.id, conn=conn)
            if total_paid_for_credit >= credit.amount:
                credit.mark_paid()
            elif total_paid_for_credit > 0:
                credit.mark_partial()
            self.credit_repository.update(credit, conn=conn)

            # Enregistrer la transaction dans le journal
            balance_after = customer.balance
            transaction = Transaction(
                customer_id=request.customer_id,
                credit_id=request.credit_id,
                payment_id=saved_payment.id,
                type="payment",
                amount=request.amount,
                balance_after=balance_after,
                description=f"Paiement {request.method} - {request.reference or 'sans référence'}",
            )
            self.transaction_repository.add(transaction, conn=conn)

            logger.info(
                "Paiement enregistré: %s (montant: %s, méthode: %s)",
                saved_payment.id, request.amount, request.method,
            )
            return saved_payment

        if self.connection_manager:
            with self.connection_manager.transaction() as conn:
                return _do_record(conn)
        else:
            # Fallback sans transaction (pour tests avec fake repositories)
            return _do_record(None)

    def get_payment(self, payment_id: str, conn=None) -> Optional[Payment]:
        """Récupère un paiement par son ID."""
        return self.payment_repository.get_by_id(payment_id, conn=conn)

    def get_customer_payments(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Payment]:
        """Récupère tous les paiements d'un client (paginé)."""
        return self.payment_repository.get_by_customer(
            customer_id, offset=offset, limit=limit, conn=conn
        )

    def get_credit_payments(
        self,
        credit_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Payment]:
        """Récupère tous les paiements liés à un crédit (paginé)."""
        return self.payment_repository.get_by_credit(
            credit_id, offset=offset, limit=limit, conn=conn
        )

    def get_all_payments(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> Tuple[List[Payment], int]:
        """
        Récupère tous les paiements (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        payments = self.payment_repository.get_all(offset=offset, limit=limit, conn=conn)
        total = self.payment_repository.count_all(conn=conn)
        return payments, total

    def update_payment(self, payment_id: str, request: UpdatePaymentRequest, conn=None) -> Payment:
        """Met à jour un paiement existant."""
        payment = self.payment_repository.get_by_id(payment_id, conn=conn)
        if not payment:
            raise ValueError(f"Paiement introuvable: {payment_id}")

        if request.amount is not None:
            payment.amount = request.amount
        if request.method is not None:
            payment.method = request.method
        if request.reference is not None:
            payment.reference = request.reference
        if request.note is not None:
            payment.note = request.note

        updated = self.payment_repository.update(payment, conn=conn)
        logger.info("Paiement mis à jour: %s", payment_id)
        return updated

    def delete_payment(self, payment_id: str, conn=None) -> None:
        """Supprime un paiement."""
        self.payment_repository.delete(payment_id, conn=conn)
        logger.info("Paiement supprimé: %s", payment_id)