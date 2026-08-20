"""Ecahier - Credit DTOs (Data Transfer Objects)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class CreateCreditRequest(BaseModel):
    """DTO pour la création d'un crédit."""
    customer_id: str = Field(..., description="ID du client")
    amount: Decimal = Field(..., gt=0, description="Montant du crédit en FCFA")
    description: str = Field(default="", max_length=500, description="Description")
    due_date: Optional[datetime] = Field(None, description="Date d'échéance")

    @validator("customer_id")
    def validate_customer_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("L'ID du client est obligatoire.")
        return v.strip()


class UpdateCreditRequest(BaseModel):
    """DTO pour la mise à jour d'un crédit."""
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = Field(None, max_length=500)
    due_date: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(pending|partial|paid|cancelled)$")


class CreditResponse(BaseModel):
    """DTO de réponse pour un crédit."""
    id: str
    customer_id: str
    amount: Decimal
    description: str
    due_date: datetime
    status: str
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    sync_status: str

    class Config:
        from_attributes = True


class CreditListResponse(BaseModel):
    """DTO de réponse pour une liste de crédits."""
    credits: List[CreditResponse]
    total: int
    page: int = 1
    page_size: int = 50