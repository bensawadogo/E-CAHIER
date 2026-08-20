"""
Ecahier - Transaction Entity
Cœur métier : une transaction est un journal des opérations
(crédit ou paiement) effectué sur un compte client.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

VALID_TRANSACTION_TYPES = {"credit", "payment"}
VALID_SYNC_STATUSES = {"pending", "synced", "conflict"}


@dataclass
class Transaction:
    """Entité Transaction — journal des opérations d'un client."""

    id: str = field(default_factory=lambda: str(uuid4()))
    customer_id: str = ""
    credit_id: str = ""
    payment_id: str = ""
    type: str = "credit"  # credit | payment
    amount: Decimal = Decimal("0.0")
    balance_after: Decimal = Decimal("0.0")
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sync_status: str = "pending"  # pending | synced | conflict

    def __post_init__(self) -> None:
        """Valide les champs après l'initialisation."""
        if self.customer_id is None or not self.customer_id.strip():
            raise ValueError("L'ID du client est obligatoire.")
        if self.type not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"type doit être l'un de {VALID_TRANSACTION_TYPES}, "
                f"reçu : '{self.type}'."
            )
        if self.amount <= 0:
            raise ValueError("Le montant de la transaction doit être positif.")
        if self.sync_status not in VALID_SYNC_STATUSES:
            raise ValueError(
                f"sync_status doit être l'un de {VALID_SYNC_STATUSES}, "
                f"reçu : '{self.sync_status}'."
            )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, customer_id={self.customer_id!r}, "
            f"type={self.type!r}, amount={self.amount!r}, "
            f"balance_after={self.balance_after!r}, "
            f"sync_status={self.sync_status!r})"
        )

    @property
    def is_credit(self) -> bool:
        """Vérifie si la transaction est un crédit."""
        return self.type == "credit"

    @property
    def is_payment(self) -> bool:
        """Vérifie si la transaction est un paiement."""
        return self.type == "payment"

    def mark_synced(self) -> None:
        """Marque l'entité comme synchronisée avec le serveur."""
        self.sync_status = "synced"
