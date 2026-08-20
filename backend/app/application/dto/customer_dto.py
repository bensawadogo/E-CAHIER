"""Ecahier - Customer DTOs (Data Transfer Objects)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class CreateCustomerRequest(BaseModel):
    """DTO pour la création d'un client."""
    name: str = Field(..., min_length=1, max_length=200, description="Nom du client")
    phone: str = Field(default="", max_length=20, description="Téléphone")
    address: str = Field(default="", max_length=500, description="Adresse")
    notes: str = Field(default="", max_length=1000, description="Notes")
    photo_path: str = Field(default="", description="Chemin de la photo")

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom ne peut pas être vide.")
        return v.strip()


class UpdateCustomerRequest(BaseModel):
    """DTO pour la mise à jour d'un client."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)
    photo_path: Optional[str] = Field(None)
    is_active: Optional[bool] = None


class CustomerResponse(BaseModel):
    """DTO de réponse pour un client."""
    id: str
    name: str
    phone: str
    address: str
    notes: str
    photo_path: str
    total_credit: Decimal
    total_paid: Decimal
    balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    sync_status: str

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """DTO de réponse pour une liste de clients (avec pagination)."""
    customers: List[CustomerResponse]
    total: int
    page: int = 1
    page_size: int = 50