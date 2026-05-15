# Tutorial setup Laksa — langkah demi langkah

Ikuti urutan ini dari atas ke bawah. Anggap folder proyek Anda: `~/Development/Laksa` (sesuaikan path Anda).

---

## Bagian A — Prasyarat di Mac

### A1. Python 3.11

```bash
python3.11 --version
```

Jika tidak ada: `brew install python@3.11`.

### A2. Git & (opsional) Docker Desktop

- **Docker** dipakai jika Anda memakai MySQL lewat `docker-compose.yml` di repo.
- **mysql-client** (CLI) untuk migrasi SQL:

```bash
brew install mysql-client
echo 'export PATH="/opt/homebrew/opt/mysql-client/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### A3. Node.js 22+ (hanya jika pakai OpenClaw)

```bash
node --version
```

Minimal **22.14** menurut dokumentasi OpenClaw umum. Bisa pakai `nvm install 22 && nvm use 22` jika perlu.

---

## Bagian B — Proyek Python (Laksa API)

### B1. Masuk folder & virtual environment

```bash
cd ~/Development/Laksa
python3.11 -m venv venv
source venv/bin/activate
```

Pastikan prompt ada **`(venv)`**. Setelah itu, **`python`** dan **`pip`** mengarah ke venv.

### B2. Dependensi Python

```bash
pip install -r requirements.txt
```

### B3. Berkas lingkungan

```bash
cp .env.example .env
```

Buka `.env` dengan editor dan isi minimal:

| Variabel | Keterangan |
|----------|------------|
| `ANTHROPIC_API_KEY` | Kunci API Claude |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` |
| `DB_*` | Host, port, user, password, nama DB MySQL |
| `TWILIO_*` | Untuk fallback WhatsApp (opsional tapi disarankan) |
| `DOKU_*` | Untuk track pembayaran (opsional) |
| `OPENCLAW_*` | Lihat bagian D — bisa diisi nanti |

### B4. MySQL — pilih salah satu

#### Opsi 1: MySQL lewat Docker (dari repo)

```bash
docker compose up -d
```

Tunggu ±30 detik. Lalu migrasi (password root default compose: **`laksa_root_dev`** kecuali Anda mengubahnya):

```bash
mysql -h 127.0.0.1 -P 3306 -u root -plaksa_root_dev laksa_db < db/migrations/001_initial.sql
```

Di `.env` untuk aplikasi, Anda bisa pakai user **`laksa`** / **`laksa_app_dev`** (lihat `docker-compose.yml`) atau **`root`** / **`laksa_root_dev`** — **harus sama** dengan yang dipakai MySQL. Detail: `docs/mysql-setup.md`.

#### Opsi 2: MySQL Anda sendiri (Navicat / lain)

- Buat database **`laksa_db`** (utf8mb4).
- Jalankan isi `db/migrations/001_initial.sql` (lewat Navicat atau `mysql` CLI).
- Isi `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` di `.env` **persis** seperti koneksi yang sukses di Navicat.

### B5. Seed data demo

Dengan venv masih aktif:

```bash
python db/seed.py
```

Harus muncul: `Seed selesai: business_id=1 ...`

### B6. Cek koneksi database

```bash
python3 -c "from db.connection import cek_koneksi_db_dengan_pesan; print(cek_koneksi_db_dengan_pesan())"
```

Harus `(True, '')`. Jika `(False, '...')`, baca pesan error dan `docs/mysql-setup.md` (mis. sandi salah, MySQL tidak jalan, paket `cryptography`).

### B7. Jalankan API FastAPI

**Wajib** dari venv (bukan Python 3.9 global):

```bash
source venv/bin/activate
python3 -m uvicorn main:app --reload --port 8000
```

Biarkan terminal ini terbuka.

### B8. Uji dari terminal lain

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s -X POST "http://localhost:8000/run-agent/1?tanggal=2026-05-15" | python3 -m json.tool | head -40
curl -s http://localhost:8000/report/latest/1 | python3 -m json.tool | head -30
```

Jika `database: connected` dan `run-agent` mengisi `analysis_result` / `recommendations`, **inti sistem sudah oke**.

---

## Bagian C — Webhook OpenClaw → Laksa (tanpa daemon dulu)

Di `.env` pastikan ada:

```env
OPENCLAW_GATEWAY_URL=http://localhost:18789
OPENCLAW_WEBHOOK_SECRET=laksa-openclaw-secret
OPENCLAW_PEER_PHONE=+62xxxxxxxxxx
TWILIO_FALLBACK_ONLY=true
```

Dengan **uvicorn masih jalan**, uji endpoint webhook Laksa (ini **tidak** membutuhkan gateway hidup untuk routing *menu*):

```bash
curl -s -X POST http://localhost:8000/webhook/openclaw \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Secret: laksa-openclaw-secret" \
  -d '{"channel":"whatsapp","peer":"+6289678283546","text":"menu"}' | python3 -m json.tool
```

Anda harus dapat JSON dengan field **`reply`**.

Perintah **`laporan`** akan menjalankan agen penuh (perlu DB + Anthropic); bisa lebih lama.

---

## Bagian D — OpenClaw Gateway (Node, terpisah dari Python)

Ini **di luar** venv Python. Ikuti dokumentasi resmi paket **`openclaw`** (npm) yang Anda pakai; ringkasannya biasanya:

1. **Install CLI:** `npm install -g openclaw@latest`
2. **Onboarding:** `openclaw onboard --install-daemon` (ikuti wizard).
3. **Channel WhatsApp:** `openclaw channels add --channel whatsapp` lalu login / scan QR.
4. **Konfigurasi** di `~/.openclaw/openclaw.json` (atau path yang dipakai tool): arahkan **webhook outbound** ke backend Laksa, misalnya:
   - URL: `http://localhost:8000/webhook/openclaw`
   - Secret: **sama persis** dengan `OPENCLAW_WEBHOOK_SECRET` di `.env` Laksa.
5. **Jalankan gateway:** `openclaw start` (atau perintah setara di versi Anda).

**Dua proses waktu jalan:**

| Terminal | Perintah |
|----------|----------|
| 1 | `openclaw start` (gateway, mis. port **18789**) |
| 2 | `source venv/bin/activate && python3 -m uvicorn main:app --reload --port 8000` |

### Setelah gateway hidup

```bash
curl -s http://localhost:18789/api/health
```

Jika path di instalasi Anda **bukan** `/api/health` atau `/api/send`, sesuaikan file **`tools/openclaw_client.py`** agar cocok dengan API gateway Anda.

Lalu dari HP (WhatsApp sudah link ke OpenClaw), coba kirim **`menu`** atau **`laporan`** dan pantau log uvicorn.

Detail singkat di repo: **`docs/openclaw-integration.md`**.

---

## Bagian E — Ringkasan troubleshooting

| Gejala | Tindakan |
|--------|----------|
| `ModuleNotFoundError: langgraph` | Uvicorn tidak dari venv → `source venv/bin/activate` lalu `python3 -m uvicorn ...` |
| `command not found: python` | Pakai `python3` atau aktifkan venv |
| `Connection refused` MySQL | Start MySQL / `docker compose up -d` |
| `Access denied` root@192.168.65.1 | Sandi `.env` tidak sama dengan sandi user di container → `docs/mysql-setup.md` |
| `cryptography package is required` | `pip install cryptography` atau `pip install -r requirements.txt` |
| OpenClaw tidak kirim | Cek gateway hidup, path `/api/send`, secret header, nomor `OPENCLAW_PEER_PHONE` |
| WhatsApp tidak lewat OpenClaw | Reporter fallback ke Twilio; cek `TWILIO_*` dan sandbox Twilio |

---

## Urutan “hari demo” yang disarankan

1. `docker compose up -d` (jika pakai Docker MySQL)  
2. `source venv/bin/activate` → `uvicorn`  
3. `openclaw start`  
4. Tes `GET /health` → `openclaw_gateway` / `database`  
5. Tes WhatsApp: **menu** → **laporan**  
6. Tes `GET /report/latest/1`  

Selesai. Untuk variasi DOKU dan Twilio saja, ikuti `README.md` dan `docs/openclaw-integration.md`.
