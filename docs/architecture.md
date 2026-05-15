# Arsitektur Laksa

## Alur data

1. **Sumber**: CSV (`csv_upload`), form/manual (`manual`), chat OpenClaw (`openclaw_chat`), webhook DOKU (`doku`), atau jadwal (`scheduled`).
2. **Collector**: membaca MySQL, menormalisasi record untuk analisis.
3. **Analyzer**: metrik harian (sesuai `tanggal_laporan`), skor kesehatan, aturan anomali di `tools/anomaly_detector.py`.
4. **Advisor**: satu-satunya pemanggilan LLM (Claude Sonnet) untuk rekomendasi Bahasa Indonesia.
5. **Reporter**: `INSERT` ke `reports` + `anomalies`, **WhatsApp utama lewat OpenClaw gateway** (`tools/openclaw_client.py`), fallback **Twilio**, PDF di `data/reports/`.

## Orkestrasi

`agents/orchestrator.py` menyusun LangGraph linear: `collect → analyze → advise → report`.

## API penting

| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/run-agent/{business_id}` | Demo satu klik |
| POST | `/transactions` | Transaksi manual + agen |
| POST | `/transactions/upload-csv` | Unggah CSV + agen |
| POST | `/webhook/doku` | Callback DOKU + agen |
| POST | `/webhook/openclaw` | Pesan masuk dari OpenClaw → routing chat / agen |
| GET | `/report/latest/{business_id}` | JSON laporan terakhir |
| GET | `/health` | Status + DB + OpenClaw |

## Basis data

Skema di `db/migrations/001_initial.sql` — tabel `businesses`, `transactions`, `reports`, `anomalies`.
