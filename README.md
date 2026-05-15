# Laksa

Laksa is a multi-agent financial operations API for small businesses. It ingests transactions from CSV uploads, REST endpoints, payment webhooks (DOKU), and optional WhatsApp messaging (OpenClaw gateway with optional Twilio fallback), persists data in MySQL, runs a LangGraph pipeline (collect → analyze → advise → report), and exposes results as JSON and PDF where configured. Natural-language guidance is generated with Anthropic Claude; user-facing copy in the product is Indonesian.

---

## Overview

Many small businesses record cash flow across notebooks, chats, and ad hoc spreadsheets. Laksa automates consolidation, rule-based anomaly checks, and structured recommendations so operators can act without building a full accounting stack.

---

## Features

- **LangGraph** orchestration for the agent pipeline.
- **FastAPI** REST API and OpenAPI documentation at `/docs`.
- **MySQL 8** storage; SQL migrations under `db/migrations/`.
- Rule-based anomaly detection (e.g. spend spikes vs. historical averages).
- **DOKU** integration for payment-related flows (sandbox or production URLs via configuration).
- **OpenClaw** HTTP gateway for WhatsApp; **Twilio** as an optional secondary channel.
- Sample CSV data for local testing (`data/seed_transactions.csv`).

---

## Architecture

```
Sources: CSV upload · REST · DOKU webhook · WhatsApp (OpenClaw)
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ FastAPI + LangGraph     │
                 │ collect → analyze →     │
                 │ advise → report         │
                 └─────────────────────────┘
                    │           │            │
               MySQL      Anthropic API   WhatsApp / PDF
```

Further detail: [`docs/architecture.md`](docs/architecture.md).

---

## Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ |
| API | FastAPI, Uvicorn |
| Agents | LangGraph |
| LLM | Anthropic Claude (`ANTHROPIC_MODEL`) |
| Database | MySQL 8, SQLAlchemy, PyMySQL, `cryptography` |
| Payments | DOKU |
| Messaging | OpenClaw (HTTP), Twilio (optional) |
| Tests | pytest |

---

## Prerequisites

- Python 3.11+ and `pip`.
- A reachable MySQL 8 instance, or Docker Compose as defined in `docker-compose.yml`.
- Anthropic API credentials; additional keys depend on enabled integrations.

---

## Setup

```bash
git clone https://github.com/adindamochamad/OpenClaw2026_Laksa_LaksaApp.git
cd OpenClaw2026_Laksa_LaksaApp

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with real values. The file is gitignored; use `.env.example` for variable names.

Database schema:

```bash
mysql -h HOST -P PORT -u USER -p -e "CREATE DATABASE IF NOT EXISTS laksa_db CHARACTER SET utf8mb4;"
mysql -h HOST -P PORT -u USER -p laksa_db < db/migrations/001_initial.sql
```

Optional demo seed data:

```bash
python db/seed.py
```

Docker and common connection issues: [`docs/mysql-setup.md`](docs/mysql-setup.md), full walkthrough: [`docs/tutorial-setup-lengkap.md`](docs/tutorial-setup-lengkap.md).

---

## Run the server

```bash
source venv/bin/activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: `http://localhost:8000/docs`.

---

## Quick checks

```bash
curl -s http://localhost:8000/health | python -m json.tool
curl -s -X POST "http://localhost:8000/run-agent/1?tanggal=2026-05-15" | python -m json.tool
curl -s http://localhost:8000/report/latest/1 | python -m json.tool
```

The `tanggal` query parameter aligns analysis with seeded sample dates when your system clock differs from the sample data.

---

## API summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service, database, and OpenClaw gateway status |
| POST | `/run-agent/{business_id}` | Full agent pipeline for a business |
| POST | `/webhook/doku` | DOKU callback |
| POST | `/webhook/openclaw` | Inbound OpenClaw messages |
| POST | `/transactions` | Manual transaction entry |
| POST | `/transactions/upload-csv` | CSV import (multipart) |
| GET | `/report/latest/{business_id}` | Latest report (JSON) |
| GET | `/report/weekly/{business_id}` | Rolling seven-day summary |
| GET | `/integrations/doku` | DOKU connectivity probe |

---

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/tutorial-setup-lengkap.md`](docs/tutorial-setup-lengkap.md) | End-to-end setup |
| [`docs/mysql-setup.md`](docs/mysql-setup.md) | MySQL and Docker |
| [`docs/openclaw-integration.md`](docs/openclaw-integration.md) | OpenClaw gateway |
| [`docs/architecture.md`](docs/architecture.md) | Module layout |

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## Security

- Never commit `.env`.
- Rotate any credential that was exposed in git history or logs.
- For production: HTTPS, restricted database network access, secrets via your platform’s secret store or environment injection.

---

## License

Add a `LICENSE` file when distribution terms are finalized.

---

Repository: [github.com/adindamochamad/OpenClaw2026_Laksa_LaksaApp](https://github.com/adindamochamad/OpenClaw2026_Laksa_LaksaApp)
