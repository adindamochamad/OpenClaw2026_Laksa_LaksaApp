"""Wrapper Twilio untuk WhatsApp."""

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def kirim_whatsapp(pesan: str) -> dict[str, Any]:
    """Mengirim pesan WhatsApp sandbox/production via Twilio."""
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    dari = os.getenv("TWILIO_WHATSAPP_FROM")
    ke = os.getenv("TWILIO_WHATSAPP_TO")

    if not all([sid, token, dari, ke]):
        return {"sent": False, "error": "Konfigurasi Twilio belum lengkap"}

    try:
        from twilio.rest import Client

        klien = Client(sid, token)
        pesan_obj = klien.messages.create(from_=dari, to=ke, body=pesan)
        return {"sent": True, "sid": pesan_obj.sid}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": str(exc)}
