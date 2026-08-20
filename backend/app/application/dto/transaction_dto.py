"""Ecahier - Transaction DTOs (Data Transfer Objects).

Représentation du journal des opérations (crédits et paiements) d'un client.
"""

from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    """DTO de réponse pour une transaction du journal."""

    id: str
    customer_id: str
    credit_id: str = ""
    payment_id: str = ""
    type: str
    amount: Decimal
    balance_after: Decimal
    description: str
    created_at: datetime
    sync_status: str

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """DTO de réponse pour une liste de transactions (avec pagination)."""

    transactions: List[TransactionResponse]
    total: int
    page: int = 1
    page_size: int = 50
