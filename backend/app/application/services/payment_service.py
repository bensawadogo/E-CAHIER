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
from backend.app.application.services.ledger import refresh_after_payment_change
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
            if credit.customer_id != request.customer_id:
                raise ValueError("Ce crédit n'appartient pas à ce client.")

            # Idempotence : un renvoi après coupure ne doit pas compter le
            # paiement deux fois.
            if request.id:
                existing = self.payment_repository.get_by_id(request.id, conn=conn)
                if existing:
                    if (existing.customer_id != request.customer_id
                            or existing.credit_id != request.credit_id):
                        raise ValueError(f"Identifiant déjà utilisé: {request.id}")
                    return existing

            # Créer le paiement
            extra = {"id": request.id} if request.id else {}
            payment = Payment(
                customer_id=request.customer_id,
                credit_id=request.credit_id,
                amount=request.amount,
                method=request.method,
                reference=request.reference,
                note=request.note,
                **extra,
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
        updated_since: Optional[str] = None,
    ) -> Tuple[List[Payment], int]:
        """
        Récupère tous les paiements (paginé).

        Returns:
            Tuple (liste paginée, total).
        """
        extra = {"updated_since": updated_since} if updated_since else {}
        payments = self.payment_repository.get_all(
            offset=offset, limit=limit, conn=conn, **extra
        )
        total = self.payment_repository.count_all(conn=conn, **extra)
        return payments, total

    def _atomic(self, work, conn=None):
        """Exécute ``work(conn)`` en une transaction (ou dans celle fournie)."""
        if conn is not None:
            return work(conn)
        if self.connection_manager:
            with self.connection_manager.transaction() as tx:
                return work(tx)
        return work(None)

    def _refresh(self, payment, conn) -> None:
        """Statut du crédit et totaux du client d'après les paiements restants."""
        refresh_after_payment_change(
            payment.customer_id, payment.credit_id,
            self.customer_repository, self.credit_repository,
            self.payment_repository, conn=conn,
        )

    def update_payment(self, payment_id: str, request: UpdatePaymentRequest, conn=None) -> Payment:
        """Met à jour un paiement et remet statut du crédit et totaux d'aplomb."""
        def _do(conn):
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
            self._refresh(payment, conn)
            logger.info("Paiement mis à jour: %s", payment_id)
            return updated

        return self._atomic(_do, conn)

    def delete_payment(self, payment_id: str, conn=None) -> None:
        """Supprime un paiement : le crédit redevient impayé/partiel en conséquence."""
        def _do(conn):
            payment = self.payment_repository.get_by_id(payment_id, conn=conn)
            if not payment:
                raise ValueError(f"Aucun paiement trouvé avec l'ID {payment_id}.")
            self.payment_repository.delete(payment_id, conn=conn)
            self._refresh(payment, conn)
            logger.info("Paiement supprimé: %s", payment_id)

        self._atomic(_do, conn)
