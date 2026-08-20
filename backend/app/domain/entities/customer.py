"""
SmartLedger Africa - Customer Entity
Cœur métier : un client est une personne physique ou morale
qui achète à crédit dans la boutique.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

VALID_SYNC_STATUSES = {"pending", "synced", "conflict"}


@dataclass
class Customer:
    """Entité Client — représente un client qui achète à crédit dans la boutique."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""
    photo_path: str = ""
    total_credit: Decimal = Decimal("0.0")
    total_paid: Decimal = Decimal("0.0")
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sync_status: str = "pending"  # pending | synced | conflict

    def __post_init__(self) -> None:
        """Valide les champs après l'initialisation."""
        if self.name is None or not self.name.strip():
            raise ValueError("Le nom du client est obligatoire.")
        if self.sync_status not in VALID_SYNC_STATUSES:
            raise ValueError(
                f"sync_status doit être l'un de {VALID_SYNC_STATUSES}, "
                f"reçu : '{self.sync_status}'."
            )
        if self.total_credit < 0:
            raise ValueError("total_credit ne peut pas être négatif.")
        if self.total_paid < 0:
            raise ValueError("total_paid ne peut pas être négatif.")

    def __repr__(self) -> str:
        return (
            f"Customer(id={self.id!r}, name={self.name!r}, "
            f"phone={self.phone!r}, balance={self.balance!r}, "
            f"sync_status={self.sync_status!r})"
        )

    @property
    def balance(self) -> Decimal:
        """Solde restant dû."""
        return self.total_credit - self.total_paid

    @property
    def has_outstanding_balance(self) -> bool:
        """Vérifie si le client a un solde impayé significatif."""
        return self.balance > Decimal("0.01")

    def mark_synced(self) -> None:
        """Marque l'entité comme synchronisée avec le serveur."""
        self.sync_status = "synced"
        self.updated_at = datetime.now(timezone.utc)
