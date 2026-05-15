"""Endpoint transaksi dan unggah CSV."""

import io
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder

from agents.orchestrator import laksa_agent
from db import repo
from schemas.transaction import TransaksiBuat

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _jalankan_agensi(id_bisnis: int, pemicu: str, tanggal: Optional[date] = None):
    """Membangun state awal dan menjalankan graf."""
    tanggal_efektif = tanggal or date.today()
    state_awal = {
        "business_id": id_bisnis,
        "trigger": pemicu,
        "tanggal_laporan": tanggal_efektif,
        "errors": [],
    }
    return laksa_agent.invoke(state_awal)


@router.post("")
def buat_transaksi_manual(payload: TransaksiBuat):
    """Menyimpan transaksi manual lalu menjalankan agen."""
    repo.sisipkan_transaksi(
        business_id=payload.business_id,
        jumlah=payload.amount,
        tipe=payload.type,
        kategori=payload.category,
        deskripsi=payload.description,
        sumber="manual",
        tanggal=payload.transaction_date,
    )
    hasil = _jalankan_agensi(payload.business_id, "manual", payload.transaction_date)
    return {
        "message": "Transaksi disimpan dan agen dijalankan",
        "agent_result": jsonable_encoder(hasil),
    }


@router.post("/upload-csv")
async def unggah_csv(
    business_id: int = Form(..., description="ID bisnis"),
    file: UploadFile = File(...),
    tanggal_laporan: Optional[date] = Form(
        default=None,
        description="Opsional: tanggal laporan (YYYY-MM-DD)",
    ),
):
    """Mengunggah CSV transaksi, menyimpan ke DB, lalu memicu agen."""
    isi = await file.read()
    try:
        bingkai = pd.read_csv(io.BytesIO(isi))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"CSV tidak valid: {exc}") from exc

    for _, baris in bingkai.iterrows():
        tanggal = date.fromisoformat(str(baris["date"]).strip())
        repo.sisipkan_transaksi(
            business_id=business_id,
            jumlah=Decimal(str(baris["amount"])),
            tipe=str(baris["type"]).strip(),
            kategori=str(baris.get("category", "")).strip() or None,
            deskripsi=str(baris.get("description", "")).strip() or None,
            sumber="csv_upload",
            tanggal=tanggal,
        )

    hasil = _jalankan_agensi(business_id, "csv_upload", tanggal_laporan or date.today())
    return {
        "message": "CSV diimpor dan agen dijalankan",
        "agent_result": jsonable_encoder(hasil),
    }
