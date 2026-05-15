"""Webhook DOKU."""

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder

from agents.orchestrator import laksa_agent
from db import repo
from tools import doku_client

router = APIRouter(tags=["webhook"])


@router.post("/webhook/doku")
async def webhook_doku(request: Request):
    """Menerima callback pembayaran DOKU (sandbox)."""
    payload: dict[str, Any]
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}

    ringkas = doku_client.normalisasi_payload_webhook(payload)
    id_bisnis = int(payload.get("business_id", 1))
    jumlah = ringkas.get("amount")
    if jumlah is None:
        jumlah = Decimal("0")
    else:
        jumlah = Decimal(str(jumlah))

    if jumlah > 0:
        repo.sisipkan_transaksi(
            business_id=id_bisnis,
            jumlah=jumlah,
            tipe="income",
            kategori="pembayaran_doku",
            deskripsi=f"DOKU {ringkas.get('reference') or ''}".strip(),
            sumber="doku",
            tanggal=date.today(),
            id_doku=str(ringkas.get("doku_transaction_id") or "unknown"),
        )

    hasil = laksa_agent.invoke(
        {
            "business_id": id_bisnis,
            "trigger": "webhook",
            "tanggal_laporan": date.today(),
            "errors": [],
        }
    )
    return {
        "received": True,
        "parsed": ringkas,
        "agent_result": jsonable_encoder(hasil),
    }
