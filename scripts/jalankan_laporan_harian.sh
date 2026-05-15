#!/usr/bin/env bash
# Memicu pipeline laporan harian Laksa (collect → analyze → advise → report).
# Dipanggil oleh systemd timer laksa-laporan-harian.timer (default 20:00 WIB).

set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"

if [[ ! -f .env ]]; then
  echo "ERROR: .env tidak ditemukan di $AKAR" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

ID_BISNIS="${LAPORAN_HARIAN_BUSINESS_ID:-1}"
URL_DASAR="${LAKSA_INTERNAL_URL:-http://127.0.0.1:8000}"
URL_DASAR="${URL_DASAR%/}"
BATAS_DETIK="${LAPORAN_HARIAN_TIMEOUT_DETIK:-300}"

echo "[$(date -Iseconds)] Memulai laporan harian business_id=${ID_BISNIS}"

if ! systemctl is-active --quiet laksa.service 2>/dev/null; then
  echo "ERROR: laksa.service tidak aktif" >&2
  exit 1
fi

HTTP_CODE=$(curl -sS -o /tmp/laksa_laporan_harian_terakhir.json -w "%{http_code}" \
  -X POST "${URL_DASAR}/run-agent/${ID_BISNIS}?trigger=scheduled" \
  -H "Content-Type: application/json" \
  --max-time "${BATAS_DETIK}")

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "ERROR: run-agent HTTP ${HTTP_CODE}" >&2
  head -c 2000 /tmp/laksa_laporan_harian_terakhir.json >&2 || true
  exit 1
fi

if grep -qE '"whatsapp_sent"[[:space:]]*:[[:space:]]*true' /tmp/laksa_laporan_harian_terakhir.json 2>/dev/null; then
  echo "[$(date -Iseconds)] Selesai — WhatsApp terkirim"
else
  echo "[$(date -Iseconds)] Selesai — cek errors di /tmp/laksa_laporan_harian_terakhir.json" >&2
  head -c 1500 /tmp/laksa_laporan_harian_terakhir.json >&2 || true
  exit 2
fi
