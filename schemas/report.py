"""Skema Pydantic untuk laporan."""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class RingkasanLaporan(BaseModel):
    """Ringkasan laporan untuk response API."""

    id: int
    business_id: int
    report_type: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    health_score: Optional[int] = None
    total_income: Optional[Decimal] = None
    total_expense: Optional[Decimal] = None
    net_cashflow: Optional[Decimal] = None
    anomalies_detected: Optional[list[Any]] = Field(default=None)
    recommendations: Optional[str] = None
    whatsapp_sent: bool = False
