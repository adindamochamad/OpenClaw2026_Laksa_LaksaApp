"""Klien HTTP untuk DOKU Sandbox (token + helper webhook)."""

import base64
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


def dapatkan_kredensial() -> tuple[str, str, str]:
    client_id = os.getenv("DOKU_CLIENT_ID", "")
    secret = os.getenv("DOKU_SECRET_KEY", "")
    base = os.getenv("DOKU_BASE_URL", "https://api-sandbox.doku.com").rstrip("/")
    return client_id, secret, base


def minta_token_akses() -> dict[str, Any]:
    """
    Mengambil access token DOKU (B2B) jika endpoint tersedia.
    Respons sandbox bisa berbeda; fungsi ini untuk demonstrasi integrasi payment track.
    """
    client_id, secret, base = dapatkan_kredensial()
    if not client_id or not secret:
        return {"error": "DOKU_CLIENT_ID atau DOKU_SECRET_KEY belum diisi"}

    # Contoh pola umum OAuth client credentials — sesuaikan dengan dokumentasi DOKU terbaru
    url = f"{base}/checkout/v1/payment/get-token"
    gabungan = f"{client_id}:{secret}"
    header_auth = base64.b64encode(gabungan.encode()).decode()
    try:
        with httpx.Client(timeout=15.0) as klien:
            resp = klien.post(
                url,
                headers={
                    "Authorization": f"Basic {header_auth}",
                    "Content-Type": "application/json",
                },
                json={},
            )
        return {"status_code": resp.status_code, "body": resp.text[:2000]}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def normalisasi_payload_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Mencoba menormalisasi berbagai bentuk payload webhook DOKU ke field standar.
    """
    # Field umum yang sering dipakai gateway; fallback ke snake_case generik
    referensi = (
        payload.get("invoice_number")
        or payload.get("reference_id")
        or payload.get("order", {}).get("invoice_number")
        if isinstance(payload.get("order"), dict)
        else None
    )
    jumlah = (
        payload.get("amount")
        or payload.get("total_amount")
        or payload.get("transaction", {}).get("amount")
        if isinstance(payload.get("transaction"), dict)
        else None
    )
    id_transaksi = (
        payload.get("transaction_id")
        or payload.get("originalPartnerReferenceNo")
        or payload.get("id")
    )
    return {
        "doku_transaction_id": str(id_transaksi) if id_transaksi else None,
        "amount": jumlah,
        "reference": referensi,
        "raw_keys": list(payload.keys()),
    }
