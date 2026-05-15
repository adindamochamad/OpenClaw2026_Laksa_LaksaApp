# Integrasi OpenClaw × Laksa

Ringkasan: **OpenClaw** (gateway HTTP di `:18789`) menjadi **saluran utama WhatsApp**; aplikasi Python memanggil **`POST /tools/invoke`** (tool `message`, action `send`). **Twilio** tetap **fallback** saat gateway gagal dan `TWILIO_FALLBACK_ONLY=true` (default).

## Di dalam repo Laksa (sudah diimplementasikan)

| Komponen | Lokasi |
|----------|--------|
| Klien HTTP | `tools/openclaw_client.py` |
| Webhook perintah chat | `POST /webhook/openclaw` → `api/routes/openclaw_webhook.py` |
| Notifikasi pembayaran DOKU | `tools/notifikasi_pembayaran.py` (OpenClaw dulu) |
| Reporter: OpenClaw dulu, lalu Twilio | `agents/reporter.py` |
| Health: gateway + WhatsApp ready | `GET /health` → `openclaw_gateway`, `openclaw_whatsapp_ready`, `whatsapp_channel` |

### Environment (tambahkan ke `.env`)

| Variabel | Keterangan |
|----------|------------|
| `OPENCLAW_GATEWAY_URL` | Mis. `http://127.0.0.1:18789` |
| `OPENCLAW_GATEWAY_TOKEN` | Sama dengan `gateway.auth.token` di `~/.openclaw/openclaw.json` |
| `OPENCLAW_GATEWAY_SEND_PATH` | Default `/tools/invoke` |
| `OPENCLAW_PEER_PHONE` | Nomor tujuan fallback (+62…) |
| `TWILIO_FALLBACK_ONLY` | `true` = Twilio jika OpenClaw gagal |

### Kontrak kirim pesan (OpenClaw 2026.3+)

```http
POST {OPENCLAW_GATEWAY_URL}/tools/invoke
Authorization: Bearer {OPENCLAW_GATEWAY_TOKEN}
Content-Type: application/json
x-openclaw-message-channel: whatsapp
x-openclaw-account-id: default

{"tool":"message","action":"send","args":{"to":"+6289678283546","message":"Halo"}}
```

Respons sukses: `{"ok":true,"result":...}`.

### Cek kesiapan WhatsApp

```bash
curl -s http://127.0.0.1:18789/ready -H "Authorization: Bearer $OPENCLAW_GATEWAY_TOKEN"
# ready: false + failing: ["whatsapp"] → perlu login QR
```

Atau `GET https://laksa.../health` → `openclaw_whatsapp_ready`, `whatsapp_channel`.

### Chat WhatsApp → Laksa (prioritas B)

Plugin **`laksa-bridge`** di `openclaw-plugin/laksa-bridge/` meneruskan pesan WA ke Laksa.

| Perintah (teks atau `/slash`) | Fungsi |
|-----------------------------|--------|
| `menu` | Daftar perintah |
| `laporan` | Analisis harian (balasan di chat, tanpa duplikat WA dari Reporter) |
| `status` | Skor kesehatan terakhir |
| `mingguan` | Ringkasan 7 hari |
| `masuk 50000 jualan` | Catat pemasukan |
| `keluar 100000 stok` | Catat pengeluaran |
| `+50000` / `-25000` | Pemasukan / pengeluaran singkat |

Setelah mengubah plugin, restart gateway:

```bash
systemctl --user restart openclaw-gateway.service
```

Uji dari server (tanpa HP):

```bash
bash scripts/uji_chat_whatsapp.sh menu
bash scripts/uji_chat_whatsapp.sh "masuk 25000 tes chat"
```

Uji dari HP: kirim `menu` atau `/laporan` ke nomor WhatsApp yang terhubung OpenClaw.

### Tanpa agent LLM (Jatevo dihapus)

Gateway OpenClaw untuk Laksa **tidak memakai model LLM**. Hanya:

- Plugin `laksa-bridge` → webhook Laksa
- `session.sendPolicy`: tolak balasan agent di channel `whatsapp`

Workspace agent: `/var/www/laksa/.openclaw/workspace`. Telegram dinonaktifkan di config ini.

Perintah `status` (teks biasa); slash: `/laksa-status` (bukan `/status`).

---

## Di luar repo: gateway & login WhatsApp

1. Gateway user systemd (root): `systemctl --user status openclaw-gateway`
2. **Login WhatsApp (wajib sekali / setelah sesi putus)** — CLI butuh **Node.js 22+**:

```bash
# Contoh dengan nvm
nvm install 22 && nvm use 22
openclaw channels login --channel whatsapp --account default
openclaw channels status --probe
systemctl --user restart openclaw-gateway
```

3. Pastikan nomor ada di `channels.whatsapp.allowFrom` di `openclaw.json`.
4. Konfigurasi webhook inbound ke Laksa: `http://localhost:8000/webhook/openclaw` + `OPENCLAW_WEBHOOK_SECRET`.

**Dua proses saat demo:** `openclaw-gateway` (user systemd) + `laksa.service` (uvicorn).

### Gejala umum

| Gejala | Penyebab | Tindakan |
|--------|----------|----------|
| HTTP 404 pada `/api/send` | API lama | Pakai `/tools/invoke` (sudah di klien Laksa) |
| `tool execution failed` + log *No active WhatsApp Web listener* | Sesi WA belum / putus | `channels login` + restart gateway |
| `/ready` → `failing: ["whatsapp"]` | Channel belum linked | Login QR seperti di atas |
| Pesan tetap lewat Twilio | OpenClaw gagal, fallback aktif | Perbaiki WA dulu; cek log `laksa` / `journalctl --user -u openclaw-gateway` |

---

*Sesuaikan versi OpenClaw dengan dokumentasi resmi jika field API berubah.*
