"""
Ecahier - Transaction Repository Interface (Port)
Définit le contrat pour la persistance du journal des transactions.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.app.domain.entities.transaction import Transaction


class TransactionRepository(ABC):
    """Interface pour le repository des transactions."""

    @abstractmethod
    def add(self, transaction: Transaction) -> Transaction:
        """Ajoute une nouvelle transaction au journal."""
        ...

    @abstractmethod
    def get_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Récupère une transaction par son ID. Retourne None si introuvable."""
        ...

    @abstractmethod
    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Retourne l'historique des transactions d'un client (paginable)."""
        ...

    @abstractmethod
    def get_all(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Retourne la liste de toutes les transactions (paginable)."""
        ...

    @abstractmethod
    def count_all(self) -> int:
        """Retourne le nombre total de transactions."""
        ...

    @abstractmethod
    def get_pending_sync(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Retourne les transactions en attente de synchronisation (paginable)."""
        ...

    @abstractmethod
    def delete(self, transaction_id: str) -> None:
        """Supprime une transaction par son ID. Lève ValueError si introuvable."""
        ...