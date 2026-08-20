"""Ecahier - Payment DTOs (Data Transfer Objects)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class RecordPaymentRequest(BaseModel):
    """DTO pour enregistrer un paiement."""
    customer_id: str = Field(..., description="ID du client")
    credit_id: str = Field(..., description="ID du crédit associé")
    amount: Decimal = Field(..., gt=0, description="Montant du paiement en FCFA")
    method: str = Field(default="cash", pattern="^(cash|mobile_money|bank_transfer|other)$")
    reference: str = Field(default="", max_length=100, description="Référence du paiement")
    note: str = Field(default="", max_length=500, description="Note")

    @validator("customer_id", "credit_id")
    def validate_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("L'ID est obligatoire.")
        return v.strip()


class UpdatePaymentRequest(BaseModel):
    """DTO pour la mise à jour d'un paiement."""
    amount: Optional[Decimal] = Field(None, gt=0)
    method: Optional[str] = Field(None, pattern="^(cash|mobile_money|bank_transfer|other)$")
    reference: Optional[str] = Field(None, max_length=100)
    note: Optional[str] = Field(None, max_length=500)


class PaymentResponse(BaseModel):
    """DTO de réponse pour un paiement."""
    id: str
    customer_id: str
    credit_id: str
    amount: Decimal
    method: str
    reference: str
    note: str
    payment_date: datetime
    created_at: datetime
    updated_at: datetime
    sync_status: str

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """DTO de réponse pour une liste de paiements."""
    payments: List[PaymentResponse]
    total: int
    page: int = 1
    page_size: int = 50