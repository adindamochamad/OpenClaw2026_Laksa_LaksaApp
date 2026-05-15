"""
Webhook pesan masuk dari OpenClaw Gateway → router perintah Laksa.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from services.perintah_whatsapp import proses_pesan_whatsapp

logger = logging.getLogger("laksa.openclaw_webhook")

router = APIRouter(tags=["openclaw-webhook"])

RAHASIA = os.getenv("OPENCLAW_WEBHOOK_SECRET", "")


def _verifikasi_rahasia_openclaw(request: Request) -> bool:
    """Memastikan header cocok dengan OPENCLAW_WEBHOOK_SECRET (lewati jika secret kosong)."""
    if not RAHASIA:
        return True
    header_rahasia = request.headers.get("X-OpenClaw-Secret", "")
    return header_rahasia == RAHASIA


@router.post("/webhook/openclaw")
async def webhook_openclaw(request: Request):
    """
    Payload contoh:
    {"channel":"whatsapp","peer":"+6289678283546","text":"laporan","timestamp":"..."}
    """
    if not _verifikasi_rahasia_openclaw(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        badan = await request.json()
    except Exception:  # noqa: BLE001
        badan = {}

    teks_pengguna = str(badan.get("text", "")).strip()
    nomor_pengguna = str(badan.get("peer", "")).strip()
    logger.info("OpenClaw webhook: dari %s isi=%r", nomor_pengguna, teks_pengguna)

    hasil = proses_pesan_whatsapp(teks_pengguna, nomor_pengguna)
    respons: dict = {
        "reply": hasil.get("reply", ""),
        "handled": bool(hasil.get("handled")),
    }
    if hasil.get("agent_meta"):
        respons["agent_meta"] = jsonable_encoder(hasil["agent_meta"])
    return respons
