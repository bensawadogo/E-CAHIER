"""
Ecahier - Credit Repository Interface (Port)
Définit le contrat pour la persistance des crédits.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.app.domain.entities.credit import Credit


class CreditRepository(ABC):
    """Interface pour le repository des crédits."""

    @abstractmethod
    def add(self, credit: Credit) -> Credit:
        """Ajoute un nouveau crédit et le retourne avec son ID généré."""
        ...

    @abstractmethod
    def get_by_id(self, credit_id: str) -> Optional[Credit]:
        """Récupère un crédit par son ID. Retourne None si introuvable."""
        ...

    @abstractmethod
    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Credit]:
        """Retourne les crédits d'un client (paginable)."""
        ...

    @abstractmethod
    def get_all(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Credit]:
        """Retourne la liste de tous les crédits (paginable)."""
        ...

    @abstractmethod
    def get_pending(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Credit]:
        """Retourne les crédits non payés (pending ou partial) — paginable."""
        ...

    @abstractmethod
    def get_overdue(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Credit]:
        """Retourne les crédits en retard (échéance dépassée) — paginable."""
        ...

    @abstractmethod
    def count_all(self) -> int:
        """Retourne le nombre total de crédits."""
        ...

    @abstractmethod
    def count_pending(self) -> int:
        """Retourne le nombre de crédits non payés (pending ou partial)."""
        ...

    @abstractmethod
    def count_overdue(self) -> int:
        """Retourne le nombre de crédits en retard (échéance dépassée)."""
        ...

    @abstractmethod
    def update(self, credit: Credit) -> Credit:
        """Met à jour un crédit existant. Lève ValueError si introuvable."""
        ...

    @abstractmethod
    def delete(self, credit_id: str) -> None:
        """Supprime un crédit par son ID. Lève ValueError si introuvable."""
        ...
