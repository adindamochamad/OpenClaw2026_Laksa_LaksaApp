"""Agen pengumpul data transaksi dari berbagai sumber."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from db import repo


class CollectorAgent:
    """Mengambil dan menormalisasi transaksi sesuai jenis pemicu."""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Memproses state dan mengembalikan update partial untuk LangGraph."""
        daftar_error = list(state.get("errors") or [])
        try:
            id_bisnis = int(state["business_id"])
            pemicu = state.get("trigger", "manual")
            mentah, normalisasi = self._kumpulkan(id_bisnis, pemicu, state)
            return {
                "raw_transactions": mentah,
                "normalized_transactions": normalisasi,
                "errors": daftar_error,
            }
        except Exception as exc:  # noqa: BLE001
            daftar_error.append(f"collector: {exc}")
            return {"errors": daftar_error}

    def _kumpulkan(
        self,
        id_bisnis: int,
        pemicu: str,
        state: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Memilih rentang data berdasarkan pemicu."""
        hari_ini = state.get("tanggal_laporan") or date.today()

        if pemicu == "webhook":
            # Transaksi DOKU hari ini (real-time)
            mentah = repo.ambil_transaksi_bisnis(
                id_bisnis,
                mulai=hari_ini,
                akhir=hari_ini,
                sumber="doku",
            )
            if not mentah:
                mentah = repo.ambil_transaksi_hari_ini(id_bisnis)
        elif pemicu == "csv_upload":
            mulai = hari_ini - timedelta(days=30)
            mentah = repo.ambil_transaksi_bisnis(
                id_bisnis,
                mulai=mulai,
                akhir=hari_ini,
                sumber="csv_upload",
            )
            if not mentah:
                mentah = repo.ambil_transaksi_bisnis(id_bisnis, mulai=mulai, akhir=hari_ini)
        elif pemicu == "scheduled":
            mentah = repo.ambil_transaksi_hari_ini(id_bisnis)
        elif pemicu in ("manual", "openclaw_chat"):
            mulai = hari_ini - timedelta(days=30)
            mentah = repo.ambil_transaksi_bisnis(id_bisnis, mulai=mulai, akhir=hari_ini)
        else:
            # Pemicu lain atau tidak dikenal: sama seperti jendela manual
            mulai = hari_ini - timedelta(days=30)
            mentah = repo.ambil_transaksi_bisnis(id_bisnis, mulai=mulai, akhir=hari_ini)

        normalisasi = [self._normalisasi(baris) for baris in mentah]
        return mentah, normalisasi

    @staticmethod
    def _normalisasi(baris: dict[str, Any]) -> dict[str, Any]:
        """Menyamakan bentuk record untuk Analyzer."""
        tanggal = baris["transaction_date"]
        if hasattr(tanggal, "isoformat"):
            tanggal_iso = tanggal.isoformat()
        else:
            tanggal_iso = str(tanggal)[:10]
        return {
            "id": int(baris["id"]),
            "amount": float(baris["amount"]),
            "type": baris["type"],
            "category": baris.get("category"),
            "date": tanggal_iso,
            "source": baris.get("source"),
            "description": baris.get("description"),
        }
