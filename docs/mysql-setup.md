# Setup MySQL untuk Laksa (Navicat & Docker)

## Ringkasan

Aplikasi Laksa membutuhkan **server MySQL yang sedang berjalan** dan database **`laksa_db`** berisi skema dari `db/migrations/001_initial.sql`.

---

## Opsi A — MySQL pakai Docker (disarankan jika belum ada server lokal)

### A1. Pastikan Docker Desktop (atau Docker Engine) sudah jalan

```bash
docker version
```

### A2. Jalankan container dari folder proyek Laksa

```bash
cd /path/ke/Laksa
docker compose up -d
```

Ini mempublish MySQL ke **host `127.0.0.1` port `3306`**. Password root default di compose: **`laksa_root_dev`** (bisa diubah lewat env, lihat A3).

### A3. (Opsional) Ubah password root lewat file env untuk Docker

Buat berkas `.env.docker` di folder yang sama (jangan commit):

```env
MYSQL_ROOT_PASSWORD=kata_sandi_anda
MYSQL_DATABASE=laksa_db
MYSQL_APP_PASSWORD=sandi_user_laksa
```

Jalankan:

```bash
docker compose --env-file .env.docker up -d
```

### A4. Isi `.env` aplikasi Laksa agar cocok dengan Docker

Contoh minimal:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=laksa
DB_PASSWORD=laksa_app_dev
DB_NAME=laksa_db
```

- **`DB_USER=laksa`**: user yang dibuat otomatis oleh image MySQL lewat variabel `MYSQL_USER` / `MYSQL_PASSWORD` di `docker-compose.yml` (hanya pada **inisialisasi volume pertama**).
- Kalau Anda masih memakai **`root`**, sandinya harus **persis** `MYSQL_ROOT_PASSWORD` (default compose: `laksa_root_dev`), dan volume harus dibuat dengan sandi yang sama (lihat bagian *Access denied* di bawah).

### A4b. Volume MySQL sudah pernah dibuat sebelumnya?

Variabel `MYSQL_USER` / `MYSQL_PASSWORD` **hanya diproses saat data directory kosong**. Kalau container sudah pernah jalan, user `laksa` bisa belum ada.

**Opsi 1 — reset volume (hapus semua data DB di container itu):**

```bash
docker compose down -v
docker compose up -d
```

Lalu ulangi migrasi + seed.

**Opsi 2 — buat user `laksa` manual tanpa hapus data:**

```bash
docker compose exec db mysql -uroot -p'SANDI_ROOT_ANDA' -e "
CREATE USER IF NOT EXISTS 'laksa'@'%' IDENTIFIED BY 'laksa_app_dev';
GRANT ALL PRIVILEGES ON laksa_db.* TO 'laksa'@'%';
FLUSH PRIVILEGES;
"
```

Ganti `SANDI_ROOT_ANDA` dengan password root MySQL container Anda, lalu di `.env` pakai `DB_USER=laksa` dan `DB_PASSWORD=laksa_app_dev` (atau sandi yang Anda set di perintah di atas).

### A4c. Error `Access denied for user 'root'@'192.168.65.1'`

Itu alamat **host Mac** dari sudut pandang MySQL di **Docker Desktop**. Penyebab umum:

1. **Sandi salah** — paling sering: `.env` memakai sandi lain dari yang dipakai saat volume MySQL pertama kali diinisialisasi. Coba `docker compose down -v` lalu `up` lagi dengan `MYSQL_ROOT_PASSWORD` yang Anda inginkan, lalu samakan `DB_PASSWORD` jika pakai `root`.
2. **Lebih aman**: pakai user **`laksa`** (lihat A4b) dan di `.env` **`DB_USER=laksa`** — hindari `root` dari host.

Contoh minimal:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=laksa_root_dev
DB_NAME=laksa_db
```

Sesuaikan `DB_PASSWORD` dengan `MYSQL_ROOT_PASSWORD` yang Anda pakai.

### A5. Buat tabel (migrasi) dari mesin host

Perlu klien `mysql` di PATH (bisa dari Homebrew: `brew install mysql-client`).

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p laksa_db < db/migrations/001_initial.sql
```

Atau, jika user **`laksa`** sudah ada dan Anda memakai sandi yang sama dengan `MYSQL_APP_PASSWORD`:

```bash
mysql -h 127.0.0.1 -P 3306 -u laksa -p laksa_db < db/migrations/001_initial.sql
```

### A6. Seed data demo

```bash
source venv/bin/activate
python db/seed.py
```

### A7. Verifikasi

```bash
python3 -c "from db.connection import cek_koneksi_db_dengan_pesan; print(cek_koneksi_db_dengan_pesan())"
```

Harus `(True, '')`.

---

## Opsi B — MySQL sudah ada (Anda akses lewat Navicat)

Navicat **tidak menjalankan** MySQL; ia hanya menyambung ke server yang sudah jalan (lokal, Docker, atau remote).

### B1. Di Navicat, buka koneksi yang biasa Anda pakai

Klik kanan koneksi → **Edit connection** (atau setara).

### B2. Catat nilai berikut (tab Connection)

| Di Navicat     | Di `.env` Laksa   |
|----------------|-------------------|
| Host           | `DB_HOST`         |
| Port           | `DB_PORT`         |
| User name      | `DB_USER`         |
| Password       | `DB_PASSWORD`     |

**Database** di Navicat bisa satu nama spesifik; untuk Laksa paling mudah pakai database bernama **`laksa_db`**.

### B3. Pastikan server MySQL benar-benar hidup

- Kalau koneksi Navicat ke **Docker**: jalankan container itu dulu (`docker compose up` / Docker Desktop).
- Kalau **MySQL di Mac** (Homebrew): `brew services start mysql` (atau `mysql@8.0`).
- Kalau **remote**: `DB_HOST` harus hostname/IP yang sama dengan di Navicat; firewall harus mengizinkan port MySQL.

### B4. Buat database dan tabel jika belum ada

Di Navicat: buat database `laksa_db` (utf8mb4), lalu jalankan isi file `db/migrations/001_initial.sql` (Query / Execute SQL file).

Atau dari terminal (sesuaikan host, port, user):

```bash
mysql -h HOST -P PORT -u USER -p -e "CREATE DATABASE IF NOT EXISTS laksa_db CHARACTER SET utf8mb4;"
mysql -h HOST -P PORT -u USER -p laksa_db < db/migrations/001_initial.sql
```

### B5. Sinkronkan `.env` Laksa

Isi `DB_*` **persis** seperti koneksi Navicat yang sukses di **Test Connection**.

Tips: kalau `localhost` error di Python tapi Navicat OK, coba **`DB_HOST=127.0.0.1`**.

### B6. Seed & cek

```bash
source venv/bin/activate
python db/seed.py
python3 -c "from db.connection import cek_koneksi_db; print('db ok' if cek_koneksi_db() else 'db GAGAL')"
```

---

## Troubleshooting singkat

| Gejala | Kemungkinan |
|--------|-------------|
| `Connection refused` | Server MySQL tidak jalan, atau **salah port** (bukan 3306). |
| `Unknown database 'laksa_db'` | Database belum dibuat; jalankan migrasi / buat di Navicat. |
| `Access denied ... 'root'@'192.168.65.1'` | Koneksi dari Mac ke MySQL di Docker; sandi `root` tidak cocok dengan volume, atau pakai user **`laksa`** + lihat **A4c** / **A4b**. |
| `RuntimeError: 'cryptography' package is required` | MySQL 8 + `caching_sha2_password`: jalankan `pip install cryptography` (sudah ada di `requirements.txt`). |

Setelah `db ok`, lanjutkan dengan `uvicorn main:app` dan `curl http://localhost:8000/health`.
