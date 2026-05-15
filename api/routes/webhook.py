"""Webhook DOKU."""

import json
import logging
import os
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from agents.orchestrator import laksa_agent
from db import repo
from tools import doku_client, notifikasi_pembayaran

router = APIRouter(tags=["webhook"])
log_webhook = logging.getLogger("laksa.webhook_doku")

TARGET_WEBHOOK_DOKU = "/webhook/doku"


def _lewati_verifikasi_tanda_tangan() -> bool:
    return os.getenv("DOKU_WEBHOOK_SKIP_SIGNATURE_VERIFY", "").lower() in (
        "true",
        "1",
        "yes",
    )


def _header_doku_terdeteksi(header: Any) -> bool:
    for k in header.keys():
        if k.lower() == "client-id":
            return True
    return False


def tentukan_id_bisnis_dari_webhook(payload: dict[str, Any]) -> Optional[int]:
    """
    Memilih business_id yang valid untuk FK ke `businesses`.
    Urutan: env DOKU_WEBHOOK_BUSINESS_ID, field payload, lalu ID bisnis terkecil di DB.
    """
    teks_env = os.getenv("DOKU_WEBHOOK_BUSINESS_ID", "").strip()
    if teks_env.isdigit():
        kandidat_env = int(teks_env)
        if repo.cek_bisnis_ada(kandidat_env):
            return kandidat_env
    b_payload = payload.get("business_id")
    if b_payload is not None:
        try:
            kandidat_payload = int(b_payload)
        except (TypeError, ValueError):
            pass
        else:
            if repo.cek_bisnis_ada(kandidat_payload):
                return kandidat_payload
    return repo.ambil_id_bisnis_pertama()


def _jalankan_agensi_latar_belakang(id_bisnis: int) -> None:
    try:
        laksa_agent.invoke(
            {
                "business_id": id_bisnis,
                "trigger": "webhook",
                "tanggal_laporan": date.today(),
                "errors": [],
            }
        )
    except Exception as exc:  # noqa: BLE001
        log_webhook.exception("webhook_doku agen latar belakang gagal: %s", exc)


@router.post("/webhook/doku")
async def webhook_doku(request: Request, background_tasks: BackgroundTasks):
    """Menerima callback pembayaran DOKU (sandbox/production)."""
    alamat_klien = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "-"
    )
    tubuh_mentah = await request.body()

    if _header_doku_terdeteksi(request.headers) and not _lewati_verifikasi_tanda_tangan():
        if not doku_client.verifikasi_tanda_tangan_notifikasi(
            request.headers, tubuh_mentah, TARGET_WEBHOOK_DOKU
        ):
            log_webhook.warning("webhook_doku signature_tidak_valid dari=%s", alamat_klien)
            raise HTTPException(status_code=401, detail="Signature DOKU tidak valid")

    payload: dict[str, Any]
    try:
        payload = json.loads(tubuh_mentah.decode("utf-8") if tubuh_mentah else "{}")
    except json.JSONDecodeError:
        payload = {}

    ringkas = doku_client.normalisasi_payload_webhook(payload)
    id_bisnis = tentukan_id_bisnis_dari_webhook(payload)
    jumlah = ringkas.get("amount")
    if jumlah is None:
        jumlah = Decimal("0")
    else:
        jumlah = Decimal(str(jumlah))

    log_webhook.info(
        "webhook_doku dari=%s business_id=%s sukses=%s kunci=%s nominal=%s ref=%s",
        alamat_klien,
        id_bisnis,
        ringkas.get("payment_success"),
        list(payload.keys())[:12],
        str(jumlah),
        ringkas.get("reference"),
    )

    if id_bisnis is None:
        log_webhook.error(
            "webhook_doku tidak_ada_bisnis — isi businesses atau DOKU_WEBHOOK_BUSINESS_ID"
        )
        return {
            "received": True,
            "parsed": ringkas,
            "error": "Tidak ada bisnis di database; transaksi tidak disimpan.",
        }

    if not ringkas.get("payment_success", True):
        log_webhook.info(
            "webhook_doku diabaikan status=%s", ringkas.get("transaction_status")
        )
        return {
            "received": True,
            "business_id": id_bisnis,
            "skipped": True,
            "reason": "status_bukan_sukses",
            "parsed": ringkas,
        }

    id_doku = str(ringkas.get("doku_transaction_id") or "unknown")
    id_transaksi_baru: Optional[int] = None
    duplikat = False

    if id_doku != "unknown":
        ada = repo.ambil_transaksi_dari_id_doku(id_doku)
        if ada:
            id_transaksi_baru = int(ada["id"])
            duplikat = True
            log_webhook.info("webhook_doku duplikat id_doku=%s tx_id=%s", id_doku, id_transaksi_baru)

    if not duplikat and jumlah > 0:
        id_transaksi_baru = repo.sisipkan_transaksi(
            business_id=id_bisnis,
            jumlah=jumlah,
            tipe="income",
            kategori="pembayaran_doku",
            deskripsi=f"DOKU {ringkas.get('reference') or ''}".strip(),
            sumber="doku",
            tanggal=date.today(),
            id_doku=id_doku,
        )
        log_webhook.info("webhook_doku transaksi_disimpan id=%s", id_transaksi_baru)
        background_tasks.add_task(
            notifikasi_pembayaran.kirim_whatsapp_pembayaran_masuk,
            id_bisnis,
            jumlah,
            ringkas.get("reference"),
        )
        background_tasks.add_task(_jalankan_agensi_latar_belakang, id_bisnis)
    elif not duplikat:
        log_webhook.warning("webhook_doku nominal_nol — tidak insert")

    return {
        "received": True,
        "business_id": id_bisnis,
        "transaction_id": id_transaksi_baru,
        "duplicate": duplikat,
        "parsed": ringkas,
    }
