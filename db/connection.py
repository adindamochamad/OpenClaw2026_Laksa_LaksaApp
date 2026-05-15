"""Koneksi pool MySQL menggunakan SQLAlchemy + driver PyMySQL."""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.pool import QueuePool

load_dotenv()

_pooled_engine: Engine | None = None


def dapatkan_engine() -> Engine:
    """Membuat atau mengembalikan engine pool singleton."""
    global _pooled_engine
    if _pooled_engine is not None:
        return _pooled_engine

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "laksa_db")

    # URL.create meng-escape user/password (hindari rusak bila ada @, #, dll.)
    url_obj = URL.create(
        "mysql+pymysql",
        username=user,
        password=password or None,
        host=host,
        port=port,
        database=database,
        query={"charset": "utf8mb4"},
    )
    _pooled_engine = create_engine(
        url_obj,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    return _pooled_engine


@contextmanager
def dapatkan_koneksi() -> Generator:
    """Context manager untuk satu koneksi dari pool."""
    engine = dapatkan_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cek_koneksi_db() -> bool:
    """Mengecek apakah basis data dapat dijangkau."""
    try:
        with dapatkan_koneksi() as koneksi:
            koneksi.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def cek_koneksi_db_dengan_pesan() -> tuple[bool, str]:
    """
    Sama seperti cek_koneksi_db, tetapi mengembalikan pesan error untuk diagnosis.
    Berguna saat troubleshooting tanpa menebak penyebab.
    """
    try:
        with dapatkan_koneksi() as koneksi:
            koneksi.execute(text("SELECT 1"))
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
