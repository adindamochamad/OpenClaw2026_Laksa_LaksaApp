"""Notifikasi cepat setelah pembayaran DOKU (WhatsApp)."""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Optional

from db import repo
from tools import openclaw_client, twilio_client

log_notifikasi = logging.getLogger("laksa.notifikasi_pembayaran")


def kirim_whatsapp_pembayaran_masuk(
    id_bisnis: int,
    jumlah: Decimal,
    referensi: Optional[str],
) -> bool:
    """Kirim pesan singkat ke pemilik bisnis; OpenClaw utama, Twilio fallback."""
    bisnis = repo.ambil_bisnis_berdasarkan_id(id_bisnis)
    nomor = ""
    if bisnis:
        nomor = (bisnis.get("phone") or "").strip()
    if not nomor:
        nomor = openclaw_client.tentukan_nomor_peer_dari_env()

    teks_ref = referensi or "-"
    pesan = (
        "🌶️ *Laksa — Pembayaran masuk*\n"
        f"💰 Rp {jumlah:,.0f}\n"
        f"📄 Ref: {teks_ref}\n"
        "_Notifikasi otomatis dari DOKU_"
    )

    if openclaw_client.kirim_whatsapp_lewat_openclaw(nomor, pesan):
        log_notifikasi.info("WhatsApp pembayaran via openclaw ke %s", nomor)
        return True

    izinkan_twilio = os.getenv("TWILIO_FALLBACK_ONLY", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if izinkan_twilio:
        hasil: dict[str, Any] = twilio_client.kirim_whatsapp(pesan)
        if hasil.get("sent"):
            log_notifikasi.info("WhatsApp pembayaran via twilio (fallback) ke %s", nomor)
            return True
        log_notifikasi.warning("Twilio fallback gagal: %s", hasil.get("error"))

    log_notifikasi.warning("WhatsApp pembayaran tidak terkirim ke %s", nomor or "(kosong)")
    return False
