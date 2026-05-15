"""Agen analitik keuangan dan deteksi anomali."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db import repo
from tools import anomaly_detector


class AnalyzerAgent:
    """Menghitung metrik, skor kesehatan, dan daftar anomali."""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        daftar_error = list(state.get("errors") or [])
        try:
            id_bisnis = int(state["business_id"])
            normalisasi = state.get("normalized_transactions") or []
            tanggal_acuan = state.get("tanggal_laporan") or date.today()

            if not normalisasi:
                hasil = self._hasil_kosong(tanggal_acuan)
                return {"analysis_result": hasil, "errors": daftar_error}

            rentang_mulai = tanggal_acuan - timedelta(days=60)
            historis_penuh = repo.ambil_transaksi_bisnis(
                id_bisnis,
                mulai=rentang_mulai,
                akhir=tanggal_acuan,
            )
            daftar_untuk_aturan = [
                {
                    "id": int(b["id"]),
                    "amount": float(b["amount"]),
                    "type": b["type"],
                    "category": b.get("category"),
                    "date": b["transaction_date"].isoformat()
                    if hasattr(b["transaction_date"], "isoformat")
                    else str(b["transaction_date"])[:10],
                    "description": b.get("description"),
                }
                for b in historis_penuh
            ]

            total_masuk_hari = sum(
                Decimal(str(b["amount"])) for b in historis_penuh
                if b["type"] == "income" and _tanggal_sama(b["transaction_date"], tanggal_acuan)
            )
            total_keluar_hari = sum(
                Decimal(str(b["amount"])) for b in historis_penuh
                if b["type"] == "expense" and _tanggal_sama(b["transaction_date"], tanggal_acuan)
            )
            arus_bersih = total_masuk_hari - total_keluar_hari

            pendapatan_bulan = repo.total_pendapatan_bulan(
                id_bisnis,
                tanggal_acuan.year,
                tanggal_acuan.month,
            )

            anomali = anomaly_detector.gabungkan_semua_aturan(
                daftar_untuk_aturan,
                tanggal_acuan,
                pendapatan_bulan,
            )

            tren = self._hitung_tren_pemasukan(daftar_untuk_aturan, tanggal_acuan)
            laju_bakar = self._hitung_laju_bakar(historis_penuh, tanggal_acuan)
            skor = self._hitung_skor_kesehatan(arus_bersih, tren, laju_bakar, anomali)

            hasil = {
                "period": tanggal_acuan.isoformat(),
                "total_income": float(total_masuk_hari),
                "total_expense": float(total_keluar_hari),
                "net_cashflow": float(arus_bersih),
                "health_score": skor,
                "anomalies": anomali,
                "burn_rate_days": laju_bakar,
                "income_trend": tren,
            }
            return {"analysis_result": hasil, "errors": daftar_error}
        except Exception as exc:  # noqa: BLE001
            daftar_error.append(f"analyzer: {exc}")
            return {"errors": daftar_error}

    @staticmethod
    def _hasil_kosong(tanggal_acuan: date) -> dict[str, Any]:
        return {
            "period": tanggal_acuan.isoformat(),
            "total_income": 0.0,
            "total_expense": 0.0,
            "net_cashflow": 0.0,
            "health_score": 50,
            "anomalies": [],
            "burn_rate_days": 0,
            "income_trend": "stable",
        }

    @staticmethod
    def _hitung_tren_pemasukan(transaksi: list[dict[str, Any]], akhir: date) -> str:
        """Membandingkan total pemasukan 7 hari terakhir vs 7 hari sebelumnya."""
        def total_masuk(mulai: date, sampai: date) -> Decimal:
            jumlah = Decimal("0")
            for baris in transaksi:
                tgl = date.fromisoformat(str(baris["date"])[:10])
                if mulai <= tgl <= sampai and baris.get("type") == "income":
                    jumlah += Decimal(str(baris["amount"]))
            return jumlah

        blok_akhir_mulai = akhir - timedelta(days=6)
        blok_awal_akhir = blok_akhir_mulai - timedelta(days=1)
        blok_awal_mulai = blok_awal_akhir - timedelta(days=6)

        a = total_masuk(blok_akhir_mulai, akhir)
        b = total_masuk(blok_awal_mulai, blok_awal_akhir)
        if b <= 0:
            return "stable"
        delta = float((a - b) / b)
        if delta > 0.05:
            return "growing"
        if delta < -0.05:
            return "declining"
        return "stable"

    @staticmethod
    def _hitung_laju_bakar(
        historis: list[dict[str, Any]],
        tanggal_acuan: date,
    ) -> int:
        """
        Perkiraan hari runway jika pola pengeluaran rata-rata 7 hari terakhir dipertahankan
        dan saldo diasumsikan sama dengan arus bersih kumulatif singkat.
        """
        mulai = tanggal_acuan - timedelta(days=7)
        pengeluaran_list: list[Decimal] = []
        for i in range(7):
            h = mulai + timedelta(days=i)
            if h > tanggal_acuan:
                break
            subtotal = sum(
                Decimal(str(b["amount"])) for b in historis
                if b["type"] == "expense" and _tanggal_sama(b["transaction_date"], h)
            )
            pengeluaran_list.append(subtotal)
        if not pengeluaran_list:
            return 0
        rata_harian = sum(pengeluaran_list, start=Decimal("0")) / Decimal(len(pengeluaran_list))
        if rata_harian <= 0:
            return 999

        total_masuk = sum(
            Decimal(str(b["amount"])) for b in historis if b["type"] == "income"
        )
        total_keluar = sum(
            Decimal(str(b["amount"])) for b in historis if b["type"] == "expense"
        )
        saldo_asumsi = total_masuk - total_keluar
        if saldo_asumsi <= 0:
            return 0
        hari = int(saldo_asumsi / rata_harian)
        return max(hari, 0)

    @staticmethod
    def _hitung_skor_kesehatan(
        arus_bersih: Decimal,
        tren: str,
        laju_bakar: int,
        anomali: list[dict[str, Any]],
    ) -> int:
        """Heuristic health score 0–100 from cash flow, trend, runway, and anomalies."""
        skor = 50
        if arus_bersih > 0:
            skor += 20
        if tren == "growing":
            skor += 10
        if laju_bakar > 30:
            skor += 10
        for item in anomali:
            tingkat = item.get("severity", "medium")
            if tingkat == "high":
                skor -= 20
            elif tingkat == "medium":
                skor -= 10
            else:
                skor -= 5
        return max(0, min(100, skor))


def _tanggal_sama(nilai: Any, acuan: date) -> bool:
    if hasattr(nilai, "date"):
        nilai = nilai.date()  # type: ignore[assignment]
    if isinstance(nilai, date):
        return nilai == acuan
    return date.fromisoformat(str(nilai)[:10]) == acuan
