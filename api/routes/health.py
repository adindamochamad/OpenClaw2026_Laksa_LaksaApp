"""Endpoint kesehatan aplikasi."""

import os
from datetime import datetime

from fastapi import APIRouter

from db.connection import cek_koneksi_db
from tools import doku_client, openclaw_client

router = APIRouter(tags=["health"])


@router.get("/health")
def kesehatan():
    """Aggregated health for API, database, and integrations."""
    db_ok = cek_koneksi_db()
    openclaw_ok = openclaw_client.cek_gateway_openclaw_hidup()
    url_oc = os.getenv("OPENCLAW_GATEWAY_URL", "").strip()
    saluran_wa = (
        "openclaw"
        if url_oc and openclaw_ok
        else ("openclaw_offline" if url_oc else "twilio_only")
    )
    return {
        "status": "ok" if db_ok else "degraded",
        "waktu": datetime.utcnow().isoformat() + "Z",
        "versi_app": "0.1.0",
        "lingkungan": os.getenv("APP_ENV", "development"),
        "database": "connected" if db_ok else "disconnected",
        "openclaw_gateway": "running" if openclaw_ok else "offline",
        "whatsapp_channel": saluran_wa,
    }


@router.get("/integrations/doku")
def cek_integrasi_doku():
    """Probe ringan ke sandbox DOKU (untuk demonstrasi track pembayaran)."""
    return {"sandbox_probe": doku_client.minta_token_akses()}
