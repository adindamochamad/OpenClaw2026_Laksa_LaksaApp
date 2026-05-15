"""Entry point FastAPI Laksa."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.middleware import pasang_cors
from api.routes import agent_run, businesses, health, openclaw_webhook, reports, transactions, webhook


@asynccontextmanager
async def lifespan_aplikasi(app: FastAPI):
    """
    Startup: pastikan log webhook DOKU tampil di journal (root logger sering WARNING).
    """
    log_webhook = logging.getLogger("laksa.webhook_doku")
    if not log_webhook.handlers:
        penangan_stream = logging.StreamHandler()
        penangan_stream.setFormatter(
            logging.Formatter("%(levelname)s %(name)s: %(message)s")
        )
        log_webhook.addHandler(penangan_stream)
    log_webhook.setLevel(logging.INFO)
    log_webhook.propagate = False
    yield


app = FastAPI(
    title="Laksa",
    description="Multi-agent financial operations API for small businesses.",
    version="0.1.0",
    lifespan=lifespan_aplikasi,
)

pasang_cors(app)

app.include_router(health.router)
app.include_router(businesses.router)
app.include_router(reports.router)
app.include_router(transactions.router)
app.include_router(webhook.router)
app.include_router(openclaw_webhook.router)
app.include_router(agent_run.router)


@app.get("/")
def akar():
    """Service root: links to docs and health."""
    return {"service": "laksa", "docs": "/docs", "health": "/health"}
