"""
SmartLedger Africa - Customer Repository Interface (Port)
Définit le contrat pour la persistance des clients.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from backend.app.domain.entities.customer import Customer


class CustomerRepository(ABC):
    """Interface pour le repository des clients — suit le principe de ségrégation des interfaces."""

    @abstractmethod
    def add(self, customer: Customer) -> Customer:
        """Ajoute un nouveau client et le retourne avec son ID généré."""
        ...

    @abstractmethod
    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        """Récupère un client par son ID. Retourne None si introuvable."""
        ...

    @abstractmethod
    def get_all(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Customer]:
        """
        Retourne la liste des clients (paginable).

        Args:
            offset: Nombre d'éléments à ignorer (pagination).
            limit: Nombre maximum d'éléments à retourner (None = tout).
        """
        ...

    @abstractmethod
    def get_active(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Customer]:
        """Retourne la liste des clients actifs (paginable)."""
        ...

    @abstractmethod
    def count_all(self) -> int:
        """Retourne le nombre total de clients."""
        ...

    @abstractmethod
    def count_active(self) -> int:
        """Retourne le nombre total de clients actifs."""
        ...

    @abstractmethod
    def update(self, customer: Customer) -> Customer:
        """Met à jour un client existant. Lève ValueError si introuvable."""
        ...

    @abstractmethod
    def delete(self, customer_id: str) -> None:
        """Supprime un client par son ID. Lève ValueError si introuvable."""
        ...

    @abstractmethod
    def search_by_name(
        self,
        query: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Customer]:
        """Recherche des clients par nom (paginable, insensible à la casse)."""
        ...
