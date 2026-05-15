"""Entry point FastAPI Laksa."""

from fastapi import FastAPI

from api.middleware import pasang_cors
from api.routes import agent_run, businesses, health, openclaw_webhook, reports, transactions, webhook

app = FastAPI(
    title="Laksa",
    description="Multi-agent financial operations API for small businesses.",
    version="0.1.0",
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
