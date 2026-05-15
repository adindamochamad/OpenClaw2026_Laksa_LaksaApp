"""Endpoint laporan."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from db import repo

router = APIRouter(prefix="/report", tags=["reports"])


def _serialisasi_laporan(baris: dict[str, Any]) -> dict[str, Any]:
    """Menyamakan tipe untuk JSON response."""
    if not baris:
        return {}
    hasil = dict(baris)
    anom = hasil.get("anomalies_detected")
    if isinstance(anom, (bytes, str)):
        try:
            hasil["anomalies_detected"] = json.loads(anom)
        except json.JSONDecodeError:
            pass
    return hasil


@router.get("/latest/{business_id}")
def laporan_terakhir(business_id: int):
    """Laporan paling baru untuk bisnis."""
    baris = repo.laporan_terakhir(business_id)
    if not baris:
        raise HTTPException(status_code=404, detail="Belum ada laporan")
    return _serialisasi_laporan(baris)


@router.get("/weekly/{business_id}")
def laporan_mingguan(business_id: int):
    """Ringkasan arus kas 7 hari terakhir."""
    return repo.ringkasan_mingguan(business_id)
