"""
Ecahier - Payment Repository Interface (Port)
Définit le contrat pour la persistance des paiements.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from backend.app.domain.entities.payment import Payment


class PaymentRepository(ABC):
    """Interface pour le repository des paiements."""

    @abstractmethod
    def add(self, payment: Payment) -> Payment:
        """Ajoute un nouveau paiement et le retourne avec son ID généré."""
        ...

    @abstractmethod
    def get_by_id(self, payment_id: str) -> Optional[Payment]:
        """Récupère un paiement par son ID. Retourne None si introuvable."""
        ...

    @abstractmethod
    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Payment]:
        """Retourne les paiements d'un client (paginable)."""
        ...

    @abstractmethod
    def get_by_credit(
        self,
        credit_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Payment]:
        """Retourne les paiements liés à un crédit (paginable)."""
        ...

    @abstractmethod
    def get_all(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Payment]:
        """Retourne la liste de tous les paiements (paginable)."""
        ...

    @abstractmethod
    def count_all(self) -> int:
        """Retourne le nombre total de paiements."""
        ...

    @abstractmethod
    def total_paid_for_credit(self, credit_id: str) -> Decimal:
        """
        Retourne le total des montants payés pour un crédit (SUM SQL).

        Plus efficace qu'un chargement de tous les paiements en mémoire.
        """
        ...

    @abstractmethod
    def update(self, payment: Payment) -> Payment:
        """Met à jour un paiement existant. Lève ValueError si introuvable."""
        ...

    @abstractmethod
    def delete(self, payment_id: str) -> None:
        """Supprime un paiement par son ID. Lève ValueError si introuvable."""
        ...