"""Middleware sederhana (CORS)."""

from fastapi.middleware.cors import CORSMiddleware


def pasang_cors(app):
    """CORS terbuka untuk pengembangan lokal."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
