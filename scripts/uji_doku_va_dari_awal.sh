#!/usr/bin/env bash
# Uji end-to-end: Checkout DOKU sandbox → VA → webhook Laksa
# Jalankan di VPS: bash scripts/uji_doku_va_dari_awal.sh
# Opsi: LANGKAH=2 bash scripts/uji_doku_va_dari_awal.sh  (lewati prasyarat, langsung buat checkout)

set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"

LANGKAH="${LANGKAH:-1}"
NOMINAL="${DOKU_CHECKOUT_AMOUNT:-20000}"
CHANNEL="${DOKU_CHECKOUT_PAYMENT_METHOD:-VIRTUAL_ACCOUNT_DOKU}"
URL_WEBHOOK="${DOKU_OVERRIDE_NOTIFICATION_URL:-https://laksa.adindamochamad.com/webhook/doku}"

merah() { printf '\033[0;31m%s\033[0m\n' "$*"; }
hijau() { printf '\033[0;32m%s\033[0m\n' "$*"; }
kuning() { printf '\033[0;33m%s\033[0m\n' "$*"; }

judul() {
  echo ""
  echo "========== $* =========="
}

# --- Langkah 0: prasyarat ---
langkah_prasyarat() {
  judul "Langkah 0 — Prasyarat"

  if [[ ! -f .env ]]; then
    merah "File .env tidak ada di $AKAR"
    exit 1
  fi
  # shellcheck disable=SC1091
  set -a && source .env && set +a

  if [[ -z "${DOKU_CLIENT_ID:-}" || -z "${DOKU_SECRET_KEY:-}" ]]; then
    merah "Isi DOKU_CLIENT_ID dan DOKU_SECRET_KEY di .env"
    exit 1
  fi
  hijau "DOKU_CLIENT_ID: ${DOKU_CLIENT_ID:0:12}..."

  if ! systemctl is-active --quiet laksa.service 2>/dev/null; then
    kuning "laksa.service tidak aktif — jalankan: sudo systemctl start laksa.service"
  else
    hijau "laksa.service: aktif"
  fi

  if command -v mysql >/dev/null 2>&1 && [[ -n "${DB_PASSWORD:-}" ]]; then
    JUMLAH_BISNIS=$(mysql -u "${DB_USER:-laksa}" -p"${DB_PASSWORD}" "${DB_NAME:-laksa_db}" -Nse \
      "SELECT COUNT(*) FROM businesses;" 2>/dev/null || echo "0")
    if [[ "${JUMLAH_BISNIS}" == "0" ]]; then
      kuning "Tabel businesses kosong — menjalankan seed..."
      ./.venv/bin/python3 db/seed.py
    else
      hijau "businesses: ${JUMLAH_BISNIS} baris"
      mysql -u "${DB_USER:-laksa}" -p"${DB_PASSWORD}" "${DB_NAME:-laksa_db}" -e \
        "SELECT id, name FROM businesses LIMIT 3;" 2>/dev/null || true
    fi
  else
    kuning "Lewati cek MySQL (mysql CLI atau DB_PASSWORD tidak tersedia)"
  fi

  echo ""
  kuning "Pastikan di Back Office DOKU (sandbox), Notification URL ="
  echo "  ${URL_WEBHOOK}"
  echo "  (path /webhook/doku harus sama dengan override di checkout)"
}

# --- Langkah 1: buat sesi checkout (VA belum ada sampai dibuka di browser) ---
langkah_buat_checkout() {
  judul "Langkah 1 — Buat sesi Checkout (API)"

  export DOKU_CHECKOUT_PAYMENT_METHOD="$CHANNEL"
  export DOKU_CHECKOUT_AMOUNT="$NOMINAL"
  export DOKU_OVERRIDE_NOTIFICATION_URL="$URL_WEBHOOK"

  ./.venv/bin/python3 scripts/doku_checkout_sandbox_uji.py | tee /tmp/laksa_doku_checkout_terakhir.txt

  if ! grep -q "staging.doku.com/checkout-link" /tmp/laksa_doku_checkout_terakhir.txt 2>/dev/null; then
    merah "Tidak menemukan tautan checkout. Cek output di atas."
    exit 1
  fi

  TAUTAN=$(grep -oE 'https://staging\.doku\.com/checkout-link-v2/[^[:space:]]+' \
    /tmp/laksa_doku_checkout_terakhir.txt | head -1)
  echo "$TAUTAN" > /tmp/laksa_doku_tautan_checkout.txt
  hijau "Tautan disimpan: /tmp/laksa_doku_tautan_checkout.txt"
  echo "$TAUTAN"
}

# --- Langkah 2: instruksi browser + simulator ---
langkah_browser_dan_simulator() {
  judul "Langkah 2 — Browser: generate VA lalu bayar di simulator"

  TAUTAN=""
  if [[ -f /tmp/laksa_doku_tautan_checkout.txt ]]; then
    TAUTAN=$(cat /tmp/laksa_doku_tautan_checkout.txt)
  fi

  cat <<EOF

1) Buka tautan checkout di browser (PC/laptop):
   ${TAUTAN:-<jalankan langkah 1 dulu>}

2) Pilih metode: ${CHANNEL}
   (Default VIRTUAL_ACCOUNT_DOKU — paling sering aktif di sandbox)

3) Tunggu nomor Virtual Account muncul di halaman. Salin HANYA angka VA.

4) Pecah nomor VA:
   - COMPANY CODE  = 5 digit pertama
   - CUSTOMER NO   = sisanya

5) Simulator (DOKU VA / General):
   https://staging.doku.com/VASimulator/GeneralAction_show.doku

   Tab Inquiry  → COMPANY CODE + CUSTOMER NUMBER → submit
   Tab Payment  → REQUEST ID + AMOUNT dari hasil Inquiry (nominal: ${NOMINAL})

6) Jangan pakai invoice, token URL, atau Request-Id dari skrip sebagai nomor VA.

EOF

  if [[ "$CHANNEL" == "VIRTUAL_ACCOUNT_BCA" ]]; then
    echo "   Simulator BCA: https://staging.doku.com/VASimulator/BCAAction_show.doku"
  fi
}

# --- Langkah 3: pantau webhook ---
langkah_pantau_webhook() {
  judul "Langkah 3 — Pantau webhook (jalankan SEBELUM bayar di simulator)"

  cat <<'EOF'

Terminal terpisah — jalankan SEBELUM klik Payment di simulator:

  sudo journalctl -u laksa.service -f | grep -E 'webhook_doku|POST /webhook'

Atau cek nginx setelah bayar:

  sudo grep "POST /webhook/doku" /var/log/nginx/access.log | tail -5

Harapan: IP DOKU (bukan hanya curl Anda), status 200, log:
  webhook_doku transaksi_disimpan id=...

EOF
}

# --- Langkah 4: verifikasi database ---
langkah_verifikasi_db() {
  judul "Langkah 4 — Verifikasi database"

  if ! command -v mysql >/dev/null 2>&1 || [[ -z "${DB_PASSWORD:-}" ]]; then
    kuning "Set DB_PASSWORD di .env lalu:"
    echo "  mysql -u laksa -p laksa_db -e \"SELECT id, amount, description, source, created_at FROM transactions WHERE source='doku' ORDER BY id DESC LIMIT 5;\""
    return
  fi

  # shellcheck disable=SC1091
  set -a && source .env && set +a
  mysql -u "${DB_USER:-laksa}" -p"${DB_PASSWORD}" "${DB_NAME:-laksa_db}" -e \
    "SELECT id, business_id, amount, description, source, doku_transaction_id, created_at
     FROM transactions WHERE source='doku' ORDER BY id DESC LIMIT 5;"
}

# --- Main ---
case "$LANGKAH" in
  0) langkah_prasyarat ;;
  1)
    langkah_prasyarat
    langkah_buat_checkout
    langkah_browser_dan_simulator
    langkah_pantau_webhook
    ;;
  2)
    langkah_buat_checkout
    langkah_browser_dan_simulator
    ;;
  3) langkah_pantau_webhook ;;
  4) langkah_verifikasi_db ;;
  *)
    langkah_prasyarat
    langkah_buat_checkout
    langkah_browser_dan_simulator
    langkah_pantau_webhook
    kuning "Setelah bayar di simulator, jalankan:"
    echo "  LANGKAH=4 bash scripts/uji_doku_va_dari_awal.sh"
    ;;
esac
