"""Query basis data yang dipakai agen dan API."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text

from db.connection import dapatkan_koneksi


def ambil_transaksi_bisnis(
    business_id: int,
    mulai: Optional[date] = None,
    akhir: Optional[date] = None,
    sumber: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Mengambil transaksi untuk satu bisnis dengan filter opsional."""
    sql = """
        SELECT id, business_id, amount, type, category, description, source,
               doku_transaction_id, transaction_date, created_at
        FROM transactions
        WHERE business_id = :bid
    """
    params: dict[str, Any] = {"bid": business_id}
    if mulai is not None:
        sql += " AND transaction_date >= :mulai"
        params["mulai"] = mulai.isoformat()
    if akhir is not None:
        sql += " AND transaction_date <= :akhir"
        params["akhir"] = akhir.isoformat()
    if sumber:
        sql += " AND source = :sumber"
        params["sumber"] = sumber
    sql += " ORDER BY transaction_date ASC, id ASC"

    with dapatkan_koneksi() as koneksi:
        baris = koneksi.execute(text(sql), params).mappings().all()
    return [dict(r) for r in baris]


def ambil_transaksi_hari_ini(business_id: int) -> list[dict[str, Any]]:
    hari_ini = date.today()
    return ambil_transaksi_bisnis(business_id, mulai=hari_ini, akhir=hari_ini)


def sisipkan_transaksi(
    business_id: int,
    jumlah: Decimal,
    tipe: str,
    kategori: Optional[str],
    deskripsi: Optional[str],
    sumber: str,
    tanggal: date,
    id_doku: Optional[str] = None,
) -> int:
    """Menyisipkan satu transaksi; mengembalikan id."""
    with dapatkan_koneksi() as koneksi:
        hasil = koneksi.execute(
            text(
                """
                INSERT INTO transactions
                (business_id, amount, type, category, description, source,
                 doku_transaction_id, transaction_date)
                VALUES (:bid, :amount, :tipe, :cat, :desc, :src, :doku, :tgl)
                """
            ),
            {
                "bid": business_id,
                "amount": str(jumlah),
                "tipe": tipe,
                "cat": kategori,
                "desc": deskripsi,
                "src": sumber,
                "doku": id_doku,
                "tgl": tanggal.isoformat(),
            },
        )
        id_baru = hasil.lastrowid
    return int(id_baru)


def sisipkan_laporan(
    business_id: int,
    tipe_laporan: str,
    mulai: Optional[date],
    akhir: Optional[date],
    skor: int,
    total_masuk: Decimal,
    total_keluar: Decimal,
    arus_bersih: Decimal,
    anomali_json: str,
    rekomendasi: str,
    whatsapp_terkirim: bool,
) -> int:
    with dapatkan_koneksi() as koneksi:
        hasil = koneksi.execute(
            text(
                """
                INSERT INTO reports
                (business_id, report_type, period_start, period_end, health_score,
                 total_income, total_expense, net_cashflow, anomalies_detected,
                 recommendations, whatsapp_sent)
                VALUES
                (:bid, :rtype, :mulai, :akhir, :score, :inc, :exp, :net, CAST(:anom AS JSON), :rec, :wa)
                """
            ),
            {
                "bid": business_id,
                "rtype": tipe_laporan,
                "mulai": mulai.isoformat() if mulai else None,
                "akhir": akhir.isoformat() if akhir else None,
                "score": skor,
                "inc": str(total_masuk),
                "exp": str(total_keluar),
                "net": str(arus_bersih),
                "anom": anomali_json,
                "rec": rekomendasi,
                "wa": whatsapp_terkirim,
            },
        )
        return int(hasil.lastrowid)


def sisipkan_anomali(
    business_id: int,
    id_transaksi: Optional[int],
    tipe: str,
    tingkat: str,
    deskripsi: str,
) -> None:
    with dapatkan_koneksi() as koneksi:
        koneksi.execute(
            text(
                """
                INSERT INTO anomalies
                (business_id, transaction_id, anomaly_type, severity, description)
                VALUES (:bid, :tid, :atype, :sev, :desc)
                """
            ),
            {
                "bid": business_id,
                "tid": id_transaksi,
                "atype": tipe,
                "sev": tingkat,
                "desc": deskripsi,
            },
        )


def laporan_terakhir(business_id: int) -> Optional[dict[str, Any]]:
    with dapatkan_koneksi() as koneksi:
        baris = koneksi.execute(
            text(
                """
                SELECT * FROM reports
                WHERE business_id = :bid
                ORDER BY id DESC LIMIT 1
                """
            ),
            {"bid": business_id},
        ).mappings().fetchone()
    return dict(baris) if baris else None


def ringkasan_mingguan(business_id: int) -> dict[str, Any]:
    akhir = date.today()
    mulai = akhir - timedelta(days=6)
    txs = ambil_transaksi_bisnis(business_id, mulai=mulai, akhir=akhir)
    total_masuk = sum(Decimal(str(t["amount"])) for t in txs if t["type"] == "income")
    total_keluar = sum(Decimal(str(t["amount"])) for t in txs if t["type"] == "expense")
    return {
        "period_start": mulai.isoformat(),
        "period_end": akhir.isoformat(),
        "total_income": str(total_masuk),
        "total_expense": str(total_keluar),
        "net_cashflow": str(total_masuk - total_keluar),
        "transaction_count": len(txs),
    }


def ambil_bisnis_berdasarkan_nomor_hp(nomor: str) -> Optional[dict[str, Any]]:
    """Mencari satu bisnis berdasarkan kolom phone (beberapa format umum)."""
    if not nomor or not str(nomor).strip():
        return None
    mentah = str(nomor).strip()
    kandidat = _kandidat_nomor_hp(mentah)
    with dapatkan_koneksi() as koneksi:
        for satu in kandidat:
            baris = koneksi.execute(
                text("SELECT * FROM businesses WHERE phone = :hp LIMIT 1"),
                {"hp": satu},
            ).mappings().fetchone()
            if baris:
                return dict(baris)
    return None


def _kandidat_nomor_hp(nilai: str) -> list[str]:
    """Menghasilkan variasi string untuk dicocokkan ke kolom phone."""
    t = nilai.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    if not t:
        return []
    hasil = {t}
    if t.startswith("+62"):
        hasil.add("0" + t[3:])
    elif t.startswith("62") and len(t) > 2:
        hasil.add("+" + t)
        hasil.add("0" + t[2:])
    elif t.startswith("0") and len(t) > 1:
        hasil.add("+62" + t[1:])
    return list(hasil)


def daftar_bisnis() -> list[dict[str, Any]]:
    with dapatkan_koneksi() as koneksi:
        baris = koneksi.execute(text("SELECT * FROM businesses ORDER BY id")).mappings().all()
    return [dict(r) for r in baris]


def buat_bisnis_baru(
    nama: str,
    nama_pemilik: Optional[str],
    telepon: Optional[str],
    tipe_bisnis: str,
) -> int:
    with dapatkan_koneksi() as koneksi:
        hasil = koneksi.execute(
            text(
                """
                INSERT INTO businesses (name, owner_name, phone, business_type)
                VALUES (:nama, :pemilik, :tel, :tipe)
                """
            ),
            {
                "nama": nama,
                "pemilik": nama_pemilik,
                "tel": telepon,
                "tipe": tipe_bisnis,
            },
        )
        return int(hasil.lastrowid)


def total_pendapatan_bulan(
    business_id: int,
    tahun: int,
    bulan: int,
) -> Decimal:
    """Total pemasukan pada bulan kalender tertentu."""
    mulai = date(tahun, bulan, 1)
    if bulan == 12:
        akhir = date(tahun, 12, 31)
    else:
        akhir = date(tahun, bulan + 1, 1) - timedelta(days=1)
    txs = ambil_transaksi_bisnis(business_id, mulai=mulai, akhir=akhir)
    return sum(
        (Decimal(str(t["amount"])) for t in txs if t["type"] == "income"),
        start=Decimal("0"),
    )
