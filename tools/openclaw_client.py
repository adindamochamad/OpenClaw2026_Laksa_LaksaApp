"""
Klien HTTP ke OpenClaw Gateway (Node.js, default :18789).
Kirim WhatsApp lewat POST /tools/invoke; Twilio tetap fallback di modul lain.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

URL_GATEWAY_OPENCLAW = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18789").rstrip("/")
RAHASIA_WEBHOOK_OPENCLAW = os.getenv("OPENCLAW_WEBHOOK_SECRET", "")
TOKEN_GATEWAY_OPENCLAW = os.getenv("OPENCLAW_GATEWAY_TOKEN", "").strip()
PATH_KESEHATAN_GATEWAY = os.getenv(
    "OPENCLAW_GATEWAY_HEALTH_PATH", "/health,/api/health,/v1/health"
)
# OpenClaw 2026.3+: kirim lewat tools/invoke (bukan /api/send yang sudah tidak ada).
PATH_KIRIM_GATEWAY = os.getenv("OPENCLAW_GATEWAY_SEND_PATH", "/tools/invoke").strip() or "/tools/invoke"
PATH_SIAP_GATEWAY = os.getenv("OPENCLAW_GATEWAY_READY_PATH", "/ready").strip() or "/ready"
AKUN_WHATSAPP_OPENCLAW = os.getenv("OPENCLAW_WHATSAPP_ACCOUNT", "default").strip() or "default"


def _header_opsional_auth_gateway() -> dict[str, str]:
    """Authorization Bearer jika OPENCLAW_GATEWAY_TOKEN diisi di .env."""
    if not TOKEN_GATEWAY_OPENCLAW:
        return {}
    return {"Authorization": f"Bearer {TOKEN_GATEWAY_OPENCLAW}"}


def _header_kirim_whatsapp() -> dict[str, str]:
    """Header wajib untuk invoke tool message di channel WhatsApp."""
    header: dict[str, str] = {
        "Content-Type": "application/json",
        "x-openclaw-message-channel": "whatsapp",
        "x-openclaw-account-id": AKUN_WHATSAPP_OPENCLAW,
    }
    header.update(_header_opsional_auth_gateway())
    if RAHASIA_WEBHOOK_OPENCLAW:
        header["X-OpenClaw-Secret"] = RAHASIA_WEBHOOK_OPENCLAW
    return header


def _ekstrak_pesan_error_gateway(data: Any, teks_mentah: str) -> str:
    """Mengambil pesan error terbaca dari body JSON gateway."""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            pesan = err.get("message") or err.get("type")
            if pesan:
                return str(pesan)
        if data.get("message"):
            return str(data["message"])
    return teks_mentah[:500] if teks_mentah else "tanpa detail"


def cek_whatsapp_openclaw_siap() -> tuple[bool, Optional[list[str]]]:
    """
    True jika gateway /ready melaporkan siap (WhatsApp tidak di daftar failing).
    Mengembalikan (siap, daftar_channel_gagal).
    """
    if not URL_GATEWAY_OPENCLAW:
        return False, None
    try:
        with httpx.Client(timeout=5.0) as klien:
            respons = klien.get(
                f"{URL_GATEWAY_OPENCLAW}{PATH_SIAP_GATEWAY}",
                headers=_header_opsional_auth_gateway(),
            )
        # Gateway mengembalikan 503 saat belum ready; body JSON tetap valid.
        if respons.status_code not in (200, 503):
            return False, None
        data = respons.json()
        if not isinstance(data, dict):
            return False, None
        if data.get("ready") is True:
            return True, []
        gagal = data.get("failing")
        if isinstance(gagal, list):
            return False, [str(x) for x in gagal]
        return False, None
    except Exception:  # noqa: BLE001
        return False, None


def kirim_whatsapp_lewat_openclaw(nomor_peer: str, teks_pesan: str) -> bool:
    """
    Mengirim pesan WhatsApp ke peer melalui OpenClaw gateway (POST /tools/invoke).

    nomor_peer: format +62... (tanpa prefix whatsapp:)
    """
    if not URL_GATEWAY_OPENCLAW:
        return False
    nomor_bersih = _bersihkan_nomor_peer(nomor_peer)
    if not nomor_bersih:
        logger.warning("OpenClaw: nomor peer kosong setelah normalisasi")
        return False

    siap, channel_gagal = cek_whatsapp_openclaw_siap()
    if not siap:
        daftar = ", ".join(channel_gagal) if channel_gagal else "whatsapp"
        logger.warning(
            "OpenClaw: channel belum siap (failing: %s). "
            "Jalankan: openclaw channels login --channel whatsapp --account %s",
            daftar,
            AKUN_WHATSAPP_OPENCLAW,
        )

    body: dict[str, Any] = {
        "tool": "message",
        "action": "send",
        "args": {
            "to": nomor_bersih,
            "message": teks_pesan,
        },
    }

    try:
        with httpx.Client(timeout=30.0) as klien:
            respons = klien.post(
                f"{URL_GATEWAY_OPENCLAW}{PATH_KIRIM_GATEWAY}",
                json=body,
                headers=_header_kirim_whatsapp(),
            )
        try:
            data = respons.json()
        except Exception:  # noqa: BLE001
            data = None

        if respons.status_code == 200 and isinstance(data, dict) and data.get("ok") is True:
            logger.info("OpenClaw: pesan terkirim ke %s", nomor_bersih)
            return True

        pesan_err = _ekstrak_pesan_error_gateway(data, respons.text)
        logger.error(
            "OpenClaw: gagal kirim status=%s ke=%s error=%s",
            respons.status_code,
            nomor_bersih,
            pesan_err,
        )
        if "No active WhatsApp Web listener" in pesan_err or (
            channel_gagal and "whatsapp" in channel_gagal
        ):
            logger.error(
                "OpenClaw: sesi WhatsApp belum terhubung. Login QR: "
                "openclaw channels login --channel whatsapp --account %s "
                "(butuh Node.js 22+), lalu systemctl --user restart openclaw-gateway",
                AKUN_WHATSAPP_OPENCLAW,
            )
        return False
    except httpx.ConnectError:
        logger.error("OpenClaw: gateway tidak terhubung %s", URL_GATEWAY_OPENCLAW)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenClaw: error %s", exc)
        return False


def cek_gateway_openclaw_hidup() -> bool:
    """
    True jika salah satu path health gateway merespons HTTP 200.
    """
    if not URL_GATEWAY_OPENCLAW:
        return False
    daftar_path = [p.strip() for p in PATH_KESEHATAN_GATEWAY.split(",") if p.strip()]
    header: dict[str, str] = {}
    header.update(_header_opsional_auth_gateway())
    try:
        with httpx.Client(timeout=5.0) as klien:
            for path in daftar_path:
                respons = klien.get(f"{URL_GATEWAY_OPENCLAW}{path}", headers=header)
                if respons.status_code == 200:
                    return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _bersihkan_nomor_peer(nilai: str) -> str:
    """Menghapus prefix whatsapp: dan spasi."""
    if not nilai:
        return ""
    t = nilai.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    if t and not t.startswith("+"):
        if t.startswith("62"):
            t = f"+{t}"
        elif t.startswith("0"):
            t = f"+62{t[1:]}"
    return t


def tentukan_nomor_peer_dari_env() -> str:
    """Fallback nomor tujuan dari OPENCLAW_PEER_PHONE atau TWILIO_WHATSAPP_TO."""
    eksplisit = os.getenv("OPENCLAW_PEER_PHONE", "").strip()
    if eksplisit:
        return _bersihkan_nomor_peer(eksplisit)
    tw = os.getenv("TWILIO_WHATSAPP_TO", "").strip()
    return _bersihkan_nomor_peer(tw)
