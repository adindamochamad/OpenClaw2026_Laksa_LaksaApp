# Integrasi OpenClaw × Laksa

Ringkasan: **OpenClaw** (CLI Node.js, gateway HTTP) menjadi **saluran utama WhatsApp**; aplikasi Python memanggil `POST {OPENCLAW_GATEWAY_URL}/api/send`. **Twilio** tetap dipakai sebagai **fallback** saat gateway gagal dan `TWILIO_FALLBACK_ONLY=true` (default).

## Di dalam repo Laksa (sudah diimplementasikan)

| Komponen | Lokasi |
|----------|--------|
| Klien HTTP | `tools/openclaw_client.py` |
| Webhook perintah chat | `POST /webhook/openclaw` → `api/routes/openclaw_webhook.py` |
| Reporter: OpenClaw dulu, lalu Twilio | `agents/reporter.py` |
| Health: status gateway | `GET /health` → field `openclaw_gateway`, `whatsapp_channel` |
| State agen | `nomor_peer_whatsapp` di `LaksaState` (`agents/orchestrator.py`) |
| Pemicu kolektor | `openclaw_chat` (sama jendela data dengan `manual`) |
| Lookup bisnis dari HP | `repo.ambil_bisnis_berdasarkan_nomor_hp` |

### Environment (tambahkan ke `.env`)

Lihat `.env.example`: `OPENCLAW_GATEWAY_URL`, `OPENCLAW_WEBHOOK_SECRET`, `OPENCLAW_PEER_PHONE`, `TWILIO_FALLBACK_ONLY`.

### Uji webhook dari terminal

```bash
curl -s -X POST http://localhost:8000/webhook/openclaw \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Secret: laksa-openclaw-secret" \
  -d '{"channel":"whatsapp","peer":"+6289678283546","text":"menu"}' | python3 -m json.tool
```

### Asumsi API gateway

Implementasi mengikuti kontrak umum: **`POST /api/send`** (body JSON `channel`, `peer`, `text`) dan **`GET /api/health`**. Jika versi OpenClaw Anda berbeda, sesuaikan path di `tools/openclaw_client.py`.

---

## Di luar repo (daemon OpenClaw)

Instalasi dan `~/.openclaw/openclaw.json` **tidak** di-commit. Ikuti dokumentasi resmi **openclaw** (npm) untuk:

- `npm install -g openclaw@latest`
- `openclaw onboard`, channel WhatsApp, QR login
- Konfigurasi webhook outbound ke `http://localhost:8000/webhook/openclaw` dengan secret yang sama dengan `OPENCLAW_WEBHOOK_SECRET`

**Dua proses saat demo:** terminal 1 `openclaw start` (atau setara), terminal 2 `uvicorn` + venv Python 3.11.

---

*Sesuaikan path API dengan build OpenClaw yang Anda pakai.*
