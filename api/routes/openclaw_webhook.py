"""
Webhook pesan masuk dari OpenClaw Gateway → routing perintah chat → agen Laksa.
"""

import logging
import os
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from agents.orchestrator import laksa_agent
from db import repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["openclaw-webhook"])

RAHASIA = os.getenv("OPENCLAW_WEBHOOK_SECRET", "")


def _verifikasi_rahasia_openclaw(request: Request) -> bool:
    """Memastikan header cocok dengan OPENCLAW_WEBHOOK_SECRET (lewati jika secret kosong)."""
    if not RAHASIA:
        return True
    header_rahasia = request.headers.get("X-OpenClaw-Secret", "")
    return header_rahasia == RAHASIA


def _format_waktu_laporan(baris: dict) -> str:
    """Memformat created_at laporan untuk balasan chat."""
    nilai = baris.get("created_at")
    if nilai is None:
        return "-"
    if hasattr(nilai, "strftime"):
        return nilai.strftime("%d %b %Y, %H:%M")
    return str(nilai)[:16]


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

    teks_pengguna = str(badan.get("text", "")).strip().lower()
    nomor_pengguna = str(badan.get("peer", "")).strip()
    logger.info("OpenClaw webhook: dari %s isi=%r", nomor_pengguna, teks_pengguna)

    if any(k in teks_pengguna for k in ["laporan", "report", "analisis", "cek"]):
        bisnis = repo.ambil_bisnis_berdasarkan_nomor_hp(nomor_pengguna)
        id_bisnis = int(bisnis["id"]) if bisnis else 1
        hasil = laksa_agent.invoke(
            {
                "business_id": id_bisnis,
                "trigger": "openclaw_chat",
                "tanggal_laporan": date.today(),
                "nomor_peer_whatsapp": nomor_pengguna,
                "errors": [],
            }
        )
        rekom = str(hasil.get("recommendations") or "").strip()
        potong = rekom[:900] + ("…" if len(rekom) > 900 else "")
        return {
            "reply": potong or "Laporan selesai diproses. Cek notifikasi WhatsApp Anda. 🍜",
            "agent_meta": jsonable_encoder(
                {
                    "business_id": id_bisnis,
                    "report_id": hasil.get("report_id"),
                    "whatsapp_sent": hasil.get("whatsapp_sent"),
                }
            ),
        }

    if any(k in teks_pengguna for k in ["status", "skor", "score", "sehat"]):
        lap = repo.laporan_terakhir(1)
        if lap:
            skor = lap.get("health_score") or 0
            emoji = "🟢" if skor >= 70 else "🟡" if skor >= 40 else "🔴"
            return {
                "reply": (
                    f"🍜 *Status Keuangan Laksa*\n\n"
                    f"{emoji} Skor kesehatan: *{skor}/100*\n"
                    f"📅 Update: {_format_waktu_laporan(lap)}"
                )
            }
        return {"reply": "Belum ada laporan. Ketik *laporan* untuk analisis baru."}

    if any(k in teks_pengguna for k in ["bantu", "help", "menu", "halo", "hai", "hi"]):
        return {
            "reply": (
                "🍜 *Laksa — agen keuangan UMKM*\n\n"
                "📊 Ketik *laporan* → analisis hari ini\n"
                "❤️ Ketik *status* → skor kesehatan\n"
                "📈 Ketik *mingguan* → ringkasan 7 hari\n\n"
                "_Powered by Laksa Multi-Agent_"
            )
        }

    if any(k in teks_pengguna for k in ["mingguan", "weekly", "minggu"]):
        ringkas = repo.ringkasan_mingguan(1)
        return {
            "reply": (
                "📈 *Ringkasan 7 hari*\n"
                f"Pemasukan: Rp {float(ringkas['total_income']):,.0f}\n"
                f"Pengeluaran: Rp {float(ringkas['total_expense']):,.0f}\n"
                f"Arus bersih: Rp {float(ringkas['net_cashflow']):,.0f}"
            )
        }

    return {
        "reply": (
            "🍜 Saya belum paham perintahnya.\n"
            "Ketik *menu* untuk daftar perintah."
        )
    }
