"""
Ecahier - Credit Entity
Cœur métier : un crédit est une somme due par un client
à la suite d'un achat à crédit dans la boutique.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

VALID_CREDIT_STATUSES = {"pending", "partial", "paid", "cancelled"}
VALID_SYNC_STATUSES = {"pending", "synced", "conflict"}


@dataclass
class Credit:
    """Entité Crédit — représente une dette d'un client envers la boutique."""

    id: str = field(default_factory=lambda: str(uuid4()))
    customer_id: str = ""
    amount: Decimal = Decimal("0.0")
    description: str = ""
    due_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending | partial | paid | cancelled
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sync_status: str = "pending"  # pending | synced | conflict

    def __post_init__(self) -> None:
        """Valide les champs après l'initialisation."""
        if self.customer_id is None or not self.customer_id.strip():
            raise ValueError("L'ID du client est obligatoire.")
        if self.amount <= 0:
            raise ValueError("Le montant du crédit doit être positif.")
        if self.status not in VALID_CREDIT_STATUSES:
            raise ValueError(
                f"status doit être l'un de {VALID_CREDIT_STATUSES}, "
                f"reçu : '{self.status}'."
            )
        if self.sync_status not in VALID_SYNC_STATUSES:
            raise ValueError(
                f"sync_status doit être l'un de {VALID_SYNC_STATUSES}, "
                f"reçu : '{self.sync_status}'."
            )

    def __repr__(self) -> str:
        return (
            f"Credit(id={self.id!r}, customer_id={self.customer_id!r}, "
            f"amount={self.amount!r}, status={self.status!r}, "
            f"sync_status={self.sync_status!r})"
        )

    @property
    def is_paid(self) -> bool:
        """Vérifie si le crédit est entièrement payé."""
        return self.status == "paid"

    @property
    def is_pending(self) -> bool:
        """Vérifie si le crédit est en attente de paiement."""
        return self.status == "pending"

    @property
    def is_overdue(self) -> bool:
        """Vérifie si le crédit est en retard (échéance dépassée et non payé)."""
        if self.is_paid or self.status == "cancelled":
            return False
        return datetime.now(timezone.utc) > self.due_date

    def mark_paid(self) -> None:
        """Marque le crédit comme entièrement payé."""
        self.status = "paid"
        self.updated_at = datetime.now(timezone.utc)

    def mark_partial(self) -> None:
        """Marque le crédit comme partiellement payé."""
        self.status = "partial"
        self.updated_at = datetime.now(timezone.utc)

    def mark_cancelled(self) -> None:
        """Marque le crédit comme annulé."""
        self.status = "cancelled"
        self.updated_at = datetime.now(timezone.utc)

    def mark_synced(self) -> None:
        """Marque l'entité comme synchronisée avec le serveur."""
        self.sync_status = "synced"
        self.updated_at = datetime.now(timezone.utc)
