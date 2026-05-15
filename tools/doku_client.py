"""Klien HTTP untuk DOKU Sandbox (token + helper webhook)."""

import base64
import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# Status yang dianggap pembayaran berhasil (Checkout non-SNAP + variasi)
_STATUS_SUKSES = frozenset({"SUCCESS", "PAID", "00", "SUCCESSFUL"})


def _nilai_string_dari_objek_uang(nilai: Any) -> Optional[str]:
    """Mengambil string nominal dari angka, string, atau objek DOKU {value, currency}."""
    if nilai is None:
        return None
    if isinstance(nilai, dict):
        teks = nilai.get("value")
        if teks is None:
            return None
        return str(teks).strip() or None
    if isinstance(nilai, (int, float)):
        return str(nilai)
    if isinstance(nilai, str):
        s = nilai.strip()
        return s or None
    return None


def _coba_desimal_dari_sumber(*sumber: Any) -> Optional[Decimal]:
    """Mencoba beberapa sumber (flat atau nested DOKU) hingga dapat Decimal valid."""
    for item in sumber:
        teks = _nilai_string_dari_objek_uang(item)
        if not teks:
            continue
        try:
            return Decimal(teks.replace(",", ""))
        except InvalidOperation:
            continue
    return None


def buat_digest_tubuh(teks_mentah: bytes | str) -> str:
    """Digest = Base64(SHA256(body)) — sama dengan outbound Checkout."""
    if isinstance(teks_mentah, str):
        bait = teks_mentah.encode("utf-8")
    else:
        bait = teks_mentah
    return base64.b64encode(hashlib.sha256(bait).digest()).decode("utf-8")


def verifikasi_tanda_tangan_notifikasi(
    header: Mapping[str, str],
    tubuh_mentah: bytes,
    target_permintaan: str,
) -> bool:
    """
    Memverifikasi header Signature notifikasi HTTP DOKU (non-SNAP).
    Request-Target = path saja, mis. /webhook/doku
    """
    _, kunci_rahasia, _ = dapatkan_kredensial()
    if not kunci_rahasia:
        return False

    def _ambil(nama: str) -> str:
        for k, v in header.items():
            if k.lower() == nama.lower():
                return (v or "").strip()
        return ""

    id_klien = _ambil("Client-Id")
    id_permintaan = _ambil("Request-Id")
    cap_waktu = _ambil("Request-Timestamp")
    tanda_header = _ambil("Signature")
    if not all([id_klien, id_permintaan, cap_waktu, tanda_header]):
        return False

    digest = buat_digest_tubuh(tubuh_mentah)
    komponen = (
        f"Client-Id:{id_klien}\n"
        f"Request-Id:{id_permintaan}\n"
        f"Request-Timestamp:{cap_waktu}\n"
        f"Request-Target:{target_permintaan}\n"
        f"Digest:{digest}"
    )
    diharapkan = base64.b64encode(
        hmac.new(
            kunci_rahasia.encode("utf-8"),
            komponen.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    if tanda_header.startswith("HMACSHA256="):
        tanda_header = tanda_header.split("=", 1)[1]
    return hmac.compare_digest(tanda_header, diharapkan)


def apakah_pembayaran_sukses(payload: dict[str, Any]) -> bool:
    """True jika status transaksi menandakan pembayaran sukses."""
    _, transaksi = _gabungkan_order_dan_transaksi(payload)
    status = (
        transaksi.get("status")
        or payload.get("transaction_status")
        or payload.get("status")
        or ""
    )
    if isinstance(status, (int, float)):
        status = str(int(status))
    teks = str(status).strip().upper()
    if not teks:
        # Payload uji manual (curl) tanpa field status — tetap diproses
        return True
    return teks in _STATUS_SUKSES


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


def _gabungkan_order_dan_transaksi(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Checkout JOKUL sering mengirim order/transaction di dalam request_detail (camelCase).
    Gabungan: isi dari request_detail dulu, lalu ditimpa field top-level jika ada.
    """
    order_gabungan: dict[str, Any] = {}
    transaksi_gabungan: dict[str, Any] = {}

    for kunci_rd in ("request_detail", "requestDetail"):
        blok_rd = payload.get(kunci_rd)
        if not isinstance(blok_rd, dict):
            continue
        order_rd = blok_rd.get("order")
        if isinstance(order_rd, dict):
            order_gabungan.update(order_rd)
        transaksi_rd = blok_rd.get("transaction")
        if isinstance(transaksi_rd, dict):
            transaksi_gabungan.update(transaksi_rd)

    order_atas = payload.get("order")
    if isinstance(order_atas, dict):
        order_gabungan.update(order_atas)
    transaksi_atas = payload.get("transaction")
    if isinstance(transaksi_atas, dict):
        transaksi_gabungan.update(transaksi_atas)

    return order_gabungan, transaksi_gabungan


def normalisasi_payload_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Mencoba menormalisasi berbagai bentuk payload webhook DOKU ke field standar.
    Mendukung Checkout lama, request_detail (camelCase), SNAP VA, dan debit notify (amount.value).
    """
    order, transaksi = _gabungkan_order_dan_transaksi(payload)
    info_tambahan = (
        payload.get("additionalInfo")
        if isinstance(payload.get("additionalInfo"), dict)
        else {}
    )

    # Referensi invoice / partner (snake_case dan camelCase)
    referensi = (
        payload.get("invoice_number")
        or payload.get("reference_id")
        or payload.get("trxId")
        or payload.get("partnerReferenceNo")
        or payload.get("originalPartnerReferenceNo")
        or order.get("invoice_number")
        or order.get("invoiceNumber")
        or order.get("reference_id")
    )

    # Nominal: flat, snake_case, atau objek {value, currency} seperti dokumentasi SNAP
    nominal = _coba_desimal_dari_sumber(
        payload.get("amount"),
        payload.get("totalAmount"),
        payload.get("paidAmount"),
        payload.get("total_amount"),
        payload.get("paid_amount"),
        transaksi.get("amount"),
        order.get("amount"),
        order.get("total_amount"),
        order.get("totalAmount"),
        info_tambahan.get("amount"),
        info_tambahan.get("paidAmount"),
    )

    id_transaksi = (
        payload.get("transaction_id")
        or transaksi.get("original_request_id")
        or transaksi.get("originalRequestId")
        or payload.get("trxId")
        or payload.get("paymentRequestId")
        or payload.get("originalPartnerReferenceNo")
        or payload.get("originalReferenceNo")
        or payload.get("id")
    )

    jumlah_keluaran: Optional[str] = str(nominal) if nominal is not None else None
    status_transaksi = (
        transaksi.get("status")
        or payload.get("transaction_status")
        or payload.get("status")
    )

    return {
        "doku_transaction_id": str(id_transaksi) if id_transaksi else None,
        "amount": jumlah_keluaran,
        "reference": referensi,
        "transaction_status": str(status_transaksi) if status_transaksi is not None else None,
        "payment_success": apakah_pembayaran_sukses(payload),
        "raw_keys": list(payload.keys()),
    }
