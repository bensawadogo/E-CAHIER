"""
Ecahier - Transaction Service
Orchestre les use cases liés au journal des opérations (transactions).
"""

import logging
from typing import List, Optional, Tuple

from backend.app.domain.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class TransactionService:
    """Service applicatif pour la lecture du journal des transactions."""

    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository

    def get_customer_transactions(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List:
        """Retourne l'historique des opérations d'un client (paginé)."""
        return self.transaction_repository.get_by_customer(
            customer_id, offset=offset, limit=limit
        )

    def get_all_transactions(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[List, int]:
        """Retourne l'ensemble du journal (paginé), avec le total."""
        transactions = self.transaction_repository.get_all(offset=offset, limit=limit)
        total = self.transaction_repository.count_all()
        return transactions, total
