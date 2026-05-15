"""
Klien HTTP ke OpenClaw Gateway (Node.js, default :18789).
Kirim WhatsApp lewat gateway; Twilio tetap fallback di reporter.
"""

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

URL_GATEWAY_OPENCLAW = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18789").rstrip("/")
RAHASIA_WEBHOOK_OPENCLAW = os.getenv("OPENCLAW_WEBHOOK_SECRET", "")


def kirim_whatsapp_lewat_openclaw(nomor_peer: str, teks_pesan: str) -> bool:
    """
    Mengirim pesan WhatsApp ke peer melalui OpenClaw gateway (/api/send).

    nomor_peer: format +62... (tanpa prefix whatsapp:)
    """
    if not URL_GATEWAY_OPENCLAW:
        return False
    nomor_bersih = _bersihkan_nomor_peer(nomor_peer)
    if not nomor_bersih:
        logger.warning("OpenClaw: nomor peer kosong setelah normalisasi")
        return False
    header: dict[str, str] = {"Content-Type": "application/json"}
    if RAHASIA_WEBHOOK_OPENCLAW:
        header["X-OpenClaw-Secret"] = RAHASIA_WEBHOOK_OPENCLAW
    try:
        with httpx.Client(timeout=10.0) as klien:
            respons = klien.post(
                f"{URL_GATEWAY_OPENCLAW}/api/send",
                json={
                    "channel": "whatsapp",
                    "peer": nomor_bersih,
                    "text": teks_pesan,
                },
                headers=header,
            )
        if respons.status_code == 200:
            logger.info("OpenClaw: pesan terkirim ke %s", nomor_bersih)
            return True
        logger.error(
            "OpenClaw: gagal kirim status=%s body=%s",
            respons.status_code,
            respons.text[:500],
        )
        return False
    except httpx.ConnectError:
        logger.error("OpenClaw: gateway tidak terhubung %s", URL_GATEWAY_OPENCLAW)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenClaw: error %s", exc)
        return False


def cek_gateway_openclaw_hidup() -> bool:
    """True jika GET /api/health gateway merespons 200."""
    if not URL_GATEWAY_OPENCLAW:
        return False
    try:
        with httpx.Client(timeout=5.0) as klien:
            respons = klien.get(f"{URL_GATEWAY_OPENCLAW}/api/health")
        return respons.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _bersihkan_nomor_peer(nilai: str) -> str:
    """Menghapus prefix whatsapp: dan spasi."""
    if not nilai:
        return ""
    t = nilai.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    return t


def tentukan_nomor_peer_dari_env() -> str:
    """Fallback nomor tujuan dari OPENCLAW_PEER_PHONE atau TWILIO_WHATSAPP_TO."""
    eksplisit = os.getenv("OPENCLAW_PEER_PHONE", "").strip()
    if eksplisit:
        return _bersihkan_nomor_peer(eksplisit)
    tw = os.getenv("TWILIO_WHATSAPP_TO", "").strip()
    return _bersihkan_nomor_peer(tw)
