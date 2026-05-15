"""Generator PDF laporan sederhana."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def buat_pdf_laporan(
    jalur_keluaran: str,
    judul: str,
    ringkasan: dict[str, Any],
    rekomendasi: str,
) -> str:
    """Membuat file PDF dan mengembalikan path absolut."""
    direktori = os.path.dirname(jalur_keluaran)
    if direktori:
        os.makedirs(direktori, exist_ok=True)

    c = canvas.Canvas(jalur_keluaran, pagesize=A4)
    lebar, tinggi = A4
    y = tinggi - 50
    c.setTitle(judul)
    c.drawString(50, y, judul)
    y -= 30
    c.drawString(50, y, f"Dibuat: {datetime.now().isoformat(timespec='seconds')}")
    y -= 24

    def tulis_baris(teks: str):
        nonlocal y
        c.drawString(50, y, teks[:120])
        y -= 18
        if y < 80:
            c.showPage()
            y = tinggi - 50

    for kunci, nilai in ringkasan.items():
        if isinstance(nilai, Decimal):
            nilai = str(nilai)
        tulis_baris(f"{kunci}: {nilai}")

    y -= 10
    tulis_baris("Rekomendasi:")
    for baris in rekomendasi.splitlines():
        tulis_baris(baris)

    c.save()
    return os.path.abspath(jalur_keluaran)
