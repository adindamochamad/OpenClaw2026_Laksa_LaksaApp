#!/usr/bin/env python3
"""
Skrip uji: memanggil DOKU Checkout sandbox (POST /checkout/v1/payment)
sesuai dokumentasi non-SNAP (Digest + Signature HMACSHA256).

Hasil: tautan checkout; buka di browser, pilih metode VA, salin nomor VA ke
simulator DOKU (Inquiry lalu Payment).

Default channel: VIRTUAL_ACCOUNT_DOKU (aktif di akun sandbox ini).
BCA VA sering gagal jika BIN belum dikonfigurasi di Back Office DOKU.

Body memuat additional_info.override_notification_url agar DOKU mengirim
HTTP notification ke Laksa untuk transaksi ini (lihat dokumentasi Checkout).

Env opsional:
  DOKU_CHECKOUT_PAYMENT_METHOD  — mis. VIRTUAL_ACCOUNT_DOKU (default)
  DOKU_CHECKOUT_AMOUNT          — nominal integer, default 20000
  DOKU_OVERRIDE_NOTIFICATION_URL

Jalankan dari server:
  cd /var/www/laksa && ./.venv/bin/python3 scripts/doku_checkout_sandbox_uji.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]


def _muat_env() -> None:
    akar = Path(__file__).resolve().parents[1]
    berkas_env = akar / ".env"
    if load_dotenv:
        load_dotenv(berkas_env)


def buat_digest_tubuh(teks_json: str) -> str:
    """Digest = Base64(SHA256(body)) — lihat dokumentasi DOKU sample-code."""
    bait_digest = hashlib.sha256(teks_json.encode("utf-8")).digest()
    return base64.b64encode(bait_digest).decode("utf-8")


def buat_tanda_tangan(
    id_klien: str,
    id_permintaan: str,
    cap_waktu: str,
    target_permintaan: str,
    digest: str,
    kunci_rahasia: str,
) -> str:
    """Menghitung nilai header Signature (HMACSHA256=...)."""
    komponen = (
        f"Client-Id:{id_klien}\n"
        f"Request-Id:{id_permintaan}\n"
        f"Request-Timestamp:{cap_waktu}\n"
        f"Request-Target:{target_permintaan}\n"
        f"Digest:{digest}"
    )
    tanda = base64.b64encode(
        hmac.new(
            kunci_rahasia.encode("utf-8"),
            komponen.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return f"HMACSHA256={tanda}"


# Petunjuk simulator per channel (dokumentasi DOKU sandbox)
_PANDUAN_SIMULATOR: dict[str, dict[str, str]] = {
    "VIRTUAL_ACCOUNT_BCA": {
        "url": "https://staging.doku.com/VASimulator/BCAAction_show.doku",
        "nama": "BCA VA Simulator",
        "catatan": (
            "BCA VA butuh BIN/company code aktif di Back Office DOKU. "
            "Jika halaman checkout error atau VA tidak muncul, hubungi DOKU "
            "untuk mengaktifkan BIN BCA (mis. 19006) di sandbox."
        ),
    },
    "VIRTUAL_ACCOUNT_DOKU": {
        "url": "https://staging.doku.com/VASimulator/GeneralAction_show.doku",
        "nama": "General Simulator (DOKU VA)",
        "catatan": "Pilih acquirer DOKU di dropdown simulator jika tersedia.",
    },
    "VIRTUAL_ACCOUNT_BANK_MANDIRI": {
        "url": "https://staging.doku.com/VASimulator/MandiriAction_show.doku",
        "nama": "Mandiri VA Simulator",
        "catatan": "Channel Mandiri juga perlu BIN aktif di Back Office DOKU.",
    },
    "VIRTUAL_ACCOUNT_BNI": {
        "url": "https://staging.doku.com/VASimulator/BNIAction_show.doku",
        "nama": "BNI VA Simulator",
        "catatan": "Channel BNI juga perlu BIN aktif di Back Office DOKU.",
    },
}


def _pisah_nomor_va(nomor_va: str) -> tuple[str, str]:
    """Memecah nomor VA menjadi company code (5 digit) + customer number (sisanya)."""
    angka = "".join(ch for ch in nomor_va if ch.isdigit())
    if len(angka) < 6:
        return angka[:5], angka[5:]
    return angka[:5], angka[5:]


def cetak_panduan_simulator(
    channel: str,
    nominal: int,
    nomor_invoice: str,
    url_checkout: str,
) -> None:
    """Menampilkan langkah uji bayar sandbox yang sering salah dilakukan."""
    info = _PANDUAN_SIMULATOR.get(
        channel,
        {
            "url": "https://staging.doku.com/VASimulator/GeneralAction_show.doku",
            "nama": "VA Simulator",
            "catatan": "",
        },
    )
    contoh_va = "7000000000002469"
    kode_perusahaan, nomor_pelanggan = _pisah_nomor_va(contoh_va)

    print("\n=== Panduan simulasi pembayaran (sandbox) ===\n")
    print("1. Buka tautan checkout di browser (WAJIB, jangan langsung ke simulator):")
    print(f"   {url_checkout}")
    print(f"2. Pilih metode bayar yang sama dengan channel: {channel}")
    print("3. Tunggu sampai nomor Virtual Account muncul di halaman.")
    print("   JANGAN pakai:")
    print(f"   - invoice ({nomor_invoice})")
    print("   - token di URL checkout")
    print("   - Request-Id dari output skrip")
    print("4. Pecah nomor VA (hanya angka):")
    print(f"   - COMPANY CODE  = 5 digit pertama  (contoh: {kode_perusahaan})")
    print(f"   - CUSTOMER NO   = sisa digit       (contoh: {nomor_pelanggan})")
    print(f"5. Buka simulator: {info['nama']}")
    print(f"   {info['url']}")
    print("6. Tab Inquiry: isi COMPANY CODE + CUSTOMER NUMBER → submit.")
    print("7. Tab Payment: salin REQUEST ID & AMOUNT dari hasil Inquiry.")
    print(f"   Nominal harus persis: {nominal}")
    if info.get("catatan"):
        print(f"\nCatatan: {info['catatan']}")
    print(
        "\nJika simulator menolak ('tidak valid'): VA belum dibuat (checkout belum "
        "diklik), nomor salah, atau channel VA belum diaktifkan di akun DOKU Anda."
    )


def main() -> int:
    _muat_env()

    id_klien = os.getenv("DOKU_CLIENT_ID", "").strip()
    kunci_rahasia = os.getenv("DOKU_SECRET_KEY", "").strip()
    dasar_api = os.getenv("DOKU_BASE_URL", "https://api-sandbox.doku.com").rstrip("/")

    if not id_klien or not kunci_rahasia:
        print("Error: DOKU_CLIENT_ID atau DOKU_SECRET_KEY kosong di .env", file=sys.stderr)
        return 1

    target = "/checkout/v1/payment"
    channel_bayar = os.getenv(
        "DOKU_CHECKOUT_PAYMENT_METHOD",
        "VIRTUAL_ACCOUNT_DOKU",
    ).strip()
    try:
        nominal_bayar = int(os.getenv("DOKU_CHECKOUT_AMOUNT", "20000"))
    except ValueError:
        print("Error: DOKU_CHECKOUT_AMOUNT harus angka bulat", file=sys.stderr)
        return 1
    # Invoice alfanumerik (hindari simbol untuk kompatibilitas VA)
    nomor_invoice = f"INVLAKSA{int(time.time())}"
    # Paksa URL notifikasi per transaksi (Checkout) — lihat dokumentasi DOKU
    # `additional_info.override_notification_url`. Berguna jika BO belum mengarahkan
    # notifikasi Checkout ke Laksa. Bisa diubah lewat env DOKU_OVERRIDE_NOTIFICATION_URL.
    url_notifikasi = os.getenv(
        "DOKU_OVERRIDE_NOTIFICATION_URL",
        "https://laksa.adindamochamad.com/webhook/doku",
    ).strip()
    badan = {
        "order": {
            "amount": nominal_bayar,
            "invoice_number": nomor_invoice,
        },
        "payment": {
            "payment_due_date": 60,
            "payment_method_types": [channel_bayar],
        },
        "additional_info": {
            "override_notification_url": url_notifikasi,
        },
    }
    # Penting: string JSON harus sama persis dengan yang di-digest
    teks_json = json.dumps(badan, separators=(",", ":"), ensure_ascii=False)
    digest = buat_digest_tubuh(teks_json)
    id_permintaan = str(uuid.uuid4())
    cap_waktu = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tanda = buat_tanda_tangan(id_klien, id_permintaan, cap_waktu, target, digest, kunci_rahasia)

    url = f"{dasar_api}{target}"
    header = {
        "Client-Id": id_klien,
        "Request-Id": id_permintaan,
        "Request-Timestamp": cap_waktu,
        "Signature": tanda,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as klien:
        # content= agar byte body identik dengan Digest
        resp = klien.post(url, headers=header, content=teks_json)

    print("HTTP", resp.status_code)
    print("payment_channel:", channel_bayar)
    print("amount:", nominal_bayar)
    print("invoice:", nomor_invoice)
    print("override_notification_url:", url_notifikasi)
    try:
        data = resp.json()
    except Exception:
        print(resp.text[:3000])
        return 1 if resp.status_code != 200 else 0

    print(json.dumps(data, indent=2, ensure_ascii=False)[:6000])

    if resp.status_code == 200 and isinstance(data, dict):
        respon = data.get("response") or {}
        pembayaran = respon.get("payment") or {}
        tautan = pembayaran.get("url")
        if tautan:
            print("\n--- Buka tautan ini di browser ---\n")
            print(tautan)
            cetak_panduan_simulator(channel_bayar, nominal_bayar, nomor_invoice, tautan)
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
