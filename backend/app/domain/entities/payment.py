"""
Ecahier - Payment Entity
Cœur métier : un paiement est une somme versée par un client
pour rembourser un ou plusieurs crédits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

VALID_PAYMENT_METHODS = {"cash", "mobile_money", "bank_transfer", "other"}
VALID_SYNC_STATUSES = {"pending", "synced", "conflict"}


@dataclass
class Payment:
    """Entité Paiement — représente un versement d'un client."""

    id: str = field(default_factory=lambda: str(uuid4()))
    customer_id: str = ""
    credit_id: str = ""
    amount: Decimal = Decimal("0.0")
    method: str = "cash"  # cash | mobile_money | bank_transfer | other
    reference: str = ""
    note: str = ""
    payment_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sync_status: str = "pending"  # pending | synced | conflict

    def __post_init__(self) -> None:
        """Valide les champs après l'initialisation."""
        if self.customer_id is None or not self.customer_id.strip():
            raise ValueError("L'ID du client est obligatoire.")
        if self.credit_id is None or not self.credit_id.strip():
            raise ValueError("L'ID du crédit est obligatoire.")
        if self.amount <= 0:
            raise ValueError("Le montant du paiement doit être positif.")
        if self.method not in VALID_PAYMENT_METHODS:
            raise ValueError(
                f"method doit être l'un de {VALID_PAYMENT_METHODS}, "
                f"reçu : '{self.method}'."
            )
        if self.sync_status not in VALID_SYNC_STATUSES:
            raise ValueError(
                f"sync_status doit être l'un de {VALID_SYNC_STATUSES}, "
                f"reçu : '{self.sync_status}'."
            )

    def __repr__(self) -> str:
        return (
            f"Payment(id={self.id!r}, customer_id={self.customer_id!r}, "
            f"credit_id={self.credit_id!r}, amount={self.amount!r}, "
            f"method={self.method!r}, sync_status={self.sync_status!r})"
        )

    @property
    def is_mobile_money(self) -> bool:
        """Vérifie si le paiement a été effectué via mobile money."""
        return self.method == "mobile_money"

    @property
    def is_cash(self) -> bool:
        """Vérifie si le paiement a été effectué en espèces."""
        return self.method == "cash"

    def mark_synced(self) -> None:
        """Marque l'entité comme synchronisée avec le serveur."""
        self.sync_status = "synced"
        self.updated_at = datetime.now(timezone.utc)
