"""Deteksi anomali berbasis aturan (tanpa LLM)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, TypedDict


class HasilAnomali(TypedDict, total=False):
    type: str
    severity: str
    amount: float
    avg_7_days: float
    multiplier: float
    description: str
    transaction_id: int | None


def _parse_tanggal(nilai: Any) -> date:
    if isinstance(nilai, date):
        return nilai
    return date.fromisoformat(str(nilai)[:10])


def _agregasi_harian(
    transaksi: list[dict[str, Any]],
) -> dict[date, dict[str, Decimal]]:
    """Mengelompokkan pemasukan dan pengeluaran per tanggal."""
    per_hari: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0")}
    )
    for baris in transaksi:
        tanggal = _parse_tanggal(baris["date"])
        jumlah = Decimal(str(baris["amount"]))
        if baris.get("type") == "income":
            per_hari[tanggal]["income"] += jumlah
        else:
            per_hari[tanggal]["expense"] += jumlah
    return dict(per_hari)


def deteksi_expense_spike(
    transaksi: list[dict[str, Any]],
    tanggal_acuan: date,
) -> list[HasilAnomali]:
    """
    Pengeluaran hari acuan > 2.5x rata-rata total pengeluaran harian 7 hari sebelumnya.
    """
    hasil: list[HasilAnomali] = []
    per_hari = _agregasi_harian(transaksi)
    rentang_mulai = tanggal_acuan - timedelta(days=7)
    pengeluaran_harian: list[Decimal] = []
    for i in range(7):
        h = rentang_mulai + timedelta(days=i)
        if h >= tanggal_acuan:
            break
        pengeluaran_harian.append(per_hari.get(h, {}).get("expense", Decimal("0")))

    if not pengeluaran_harian:
        return hasil

    rata = sum(pengeluaran_harian, start=Decimal("0")) / Decimal(len(pengeluaran_harian))
    if rata <= 0:
        return hasil

    pengeluaran_hari_ini = per_hari.get(tanggal_acuan, {}).get("expense", Decimal("0"))
    if pengeluaran_hari_ini > Decimal("2.5") * rata:
        pengali = float(pengeluaran_hari_ini / rata)
        hasil.append(
            {
                "type": "expense_spike",
                "severity": "high",
                "amount": float(pengeluaran_hari_ini),
                "avg_7_days": float(rata),
                "multiplier": round(pengali, 2),
                "description": (
                    f"Pengeluaran hari ini {pengali:.2f}x di atas rata-rata 7 hari terakhir"
                ),
            }
        )
    return hasil


def deteksi_income_drop(
    transaksi: list[dict[str, Any]],
    tanggal_acuan: date,
) -> list[HasilAnomali]:
    """Pemasukan hari acuan < 50% rata-rata pemasukan harian 7 hari sebelumnya."""
    hasil: list[HasilAnomali] = []
    per_hari = _agregasi_harian(transaksi)
    rentang_mulai = tanggal_acuan - timedelta(days=7)
    pemasukan_harian: list[Decimal] = []
    for i in range(7):
        h = rentang_mulai + timedelta(days=i)
        if h >= tanggal_acuan:
            break
        pemasukan_harian.append(per_hari.get(h, {}).get("income", Decimal("0")))

    if not pemasukan_harian:
        return hasil

    rata = sum(pemasukan_harian, start=Decimal("0")) / Decimal(len(pemasukan_harian))
    if rata <= 0:
        return hasil

    pemasukan_hari_ini = per_hari.get(tanggal_acuan, {}).get("income", Decimal("0"))
    if pemasukan_hari_ini < Decimal("0.5") * rata:
        hasil.append(
            {
                "type": "income_drop",
                "severity": "medium",
                "amount": float(pemasukan_hari_ini),
                "avg_7_days": float(rata),
                "multiplier": float(pemasukan_hari_ini / rata) if rata else 0.0,
                "description": (
                    "Pemasukan hari ini di bawah 50% rata-rata pemasukan 7 hari terakhir"
                ),
            }
        )
    return hasil


def deteksi_negative_cashflow(
    transaksi: list[dict[str, Any]],
    tanggal_akhir: date,
) -> list[HasilAnomali]:
    """Pengeluaran > pemasukan selama 3 hari berturut-turut (mengakhiri di tanggal_akhir)."""
    hasil: list[HasilAnomali] = []
    per_hari = _agregasi_harian(transaksi)
    urut_tanggal = sorted(per_hari.keys())
    if not urut_tanggal:
        return hasil

    runtun = 0
    hari_mulai_runtun: date | None = None
    for tanggal in urut_tanggal:
        if tanggal > tanggal_akhir:
            break
        d = per_hari[tanggal]
        if d["expense"] > d["income"]:
            if runtun == 0:
                hari_mulai_runtun = tanggal
            runtun += 1
            if runtun >= 3:
                hasil.append(
                    {
                        "type": "negative_cashflow",
                        "severity": "high",
                        "amount": float(d["expense"] - d["income"]),
                        "avg_7_days": 0.0,
                        "multiplier": 0.0,
                        "description": (
                            "Arus kas negatif (pengeluaran lebih besar dari pemasukan) "
                            "selama 3 hari berturut-turut"
                        ),
                    }
                )
                return hasil
        else:
            runtun = 0
            hari_mulai_runtun = None
    return hasil


def deteksi_large_single_transaction(
    transaksi: list[dict[str, Any]],
    total_pendapatan_bulanan: Decimal,
) -> list[HasilAnomali]:
    """Transaksi tunggal (pengeluaran) > 40% total pendapatan bulan berjalan."""
    hasil: list[HasilAnomali] = []
    if total_pendapatan_bulanan <= 0:
        return hasil
    ambang = total_pendapatan_bulanan * Decimal("0.4")
    for baris in transaksi:
        if baris.get("type") != "expense":
            continue
        jumlah = Decimal(str(baris["amount"]))
        if jumlah > ambang:
            hasil.append(
                {
                    "type": "large_single_transaction",
                    "severity": "medium",
                    "amount": float(jumlah),
                    "avg_7_days": float(total_pendapatan_bulanan),
                    "multiplier": float(jumlah / total_pendapatan_bulanan),
                    "description": (
                        "Ada transaksi pengeluaran tunggal lebih dari 40% "
                        "total pendapatan bulan ini"
                    ),
                    "transaction_id": baris.get("id"),
                }
            )
    return hasil


def gabungkan_semua_aturan(
    transaksi: list[dict[str, Any]],
    tanggal_acuan: date,
    total_pendapatan_bulanan: Decimal,
) -> list[HasilAnomali]:
    """Menjalankan seluruh aturan dan menggabungkan hasil."""
    gabungan: list[HasilAnomali] = []
    gabungan.extend(deteksi_expense_spike(transaksi, tanggal_acuan))
    gabungan.extend(deteksi_income_drop(transaksi, tanggal_acuan))
    gabungan.extend(deteksi_negative_cashflow(transaksi, tanggal_acuan))
    gabungan.extend(deteksi_large_single_transaction(transaksi, total_pendapatan_bulanan))
    return gabungan
