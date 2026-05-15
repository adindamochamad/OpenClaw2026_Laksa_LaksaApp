"""Skema Pydantic untuk transaksi."""

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TransaksiBuat(BaseModel):
    """Payload pembuatan transaksi manual."""

    business_id: int = Field(..., ge=1)
    amount: Decimal = Field(..., gt=0)
    type: Literal["income", "expense"]
    category: Optional[str] = None
    description: Optional[str] = None
    transaction_date: date


class TransaksiResponse(BaseModel):
    """Response singkat setelah transaksi disimpan."""

    id: int
    business_id: int
    message: str = "Transaksi tersimpan"
