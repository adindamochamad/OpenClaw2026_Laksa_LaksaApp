#!/usr/bin/env bash
# Uji router chat Laksa (sama payload dengan plugin OpenClaw).
set -euo pipefail
AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"
# shellcheck disable=SC1091
set -a && source .env && set +a
RAHASIA="${OPENCLAW_WEBHOOK_SECRET:-}"
URL="${LAKSA_INTERNAL_URL:-http://127.0.0.1:8000}/webhook/openclaw"
PEER="${OPENCLAW_PEER_PHONE:-+6289678283546}"
TEKS="${1:-menu}"

curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Secret: $RAHASIA" \
  -d "{\"channel\":\"whatsapp\",\"peer\":\"$PEER\",\"text\":\"$TEKS\"}" | python3 -m json.tool
