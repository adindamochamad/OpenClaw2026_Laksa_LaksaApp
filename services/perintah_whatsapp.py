"""
Router perintah chat WhatsApp → logika bisnis Laksa.
Dipanggil dari POST /webhook/openclaw (dan plugin OpenClaw laksa-bridge).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from agents.orchestrator import laksa_agent
from agents.reporter import ReporterAgent
from db import repo

log_perintah = logging.getLogger("laksa.perintah_whatsapp")

# Pola: masuk/keluar/pemasukan/pengeluaran + nominal + keterangan opsional
POLA_TRANSAKSI = re.compile(
    r"^(?P<arah>masuk|keluar|pemasukan|pengeluaran|income|expense|in|out)"
    r"(?:\s+(?P<jumlah_raw>[\d.,]+(?:\s*(?:rb|ribu|k|jt|juta))?))?"
    r"(?:\s+(?P<ket>.+))?$",
    re.IGNORECASE,
)
POLA_SINGKAT = re.compile(
    r"^(?P<tanda>[+\-])\s*(?P<jumlah_raw>[\d.,]+(?:\s*(?:rb|ribu|k|jt|juta))?)"
    r"(?:\s+(?P<ket>.+))?$",
    re.IGNORECASE,
)


def proses_pesan_whatsapp(teks: str, nomor_pengirim: str) -> dict[str, Any]:
    """
    Mengolah satu pesan masuk; mengembalikan dict dengan kunci:
    handled (bool), reply (str), agent_meta (opsional).
    """
    teks_asli = (teks or "").strip()
    teks_norm = teks_asli.lower()
    if not teks_norm:
        return _belum_dipahami()

    id_bisnis, nama_bisnis = _resolve_bisnis(nomor_pengirim)

    if _cocok_perintah(teks_norm, ("menu", "bantu", "help", "halo", "hai", "hi")):
        return {"handled": True, "reply": _teks_menu(nama_bisnis)}

    if _cocok_perintah(teks_norm, ("status", "skor", "score", "sehat")):
        return {"handled": True, "reply": _teks_status(id_bisnis)}

    if _cocok_perintah(teks_norm, ("mingguan", "weekly", "minggu")):
        return {"handled": True, "reply": _teks_mingguan(id_bisnis)}

    if _cocok_perintah(teks_norm, ("laporan", "report", "analisis", "cek")):
        return _jalankan_laporan_chat(id_bisnis, nomor_pengirim)

    hasil_tx = _coba_catat_transaksi(teks_asli, id_bisnis)
    if hasil_tx:
        return hasil_tx

    return _belum_dipahami()


def _resolve_bisnis(nomor: str) -> tuple[int, str]:
    bisnis = repo.ambil_bisnis_berdasarkan_nomor_hp(nomor)
    if bisnis:
        return int(bisnis["id"]), str(bisnis.get("name") or "Bisnis")
    id_pertama = repo.ambil_id_bisnis_pertama()
    return (id_pertama if id_pertama is not None else 1), "Warung Laksa Demo"


def _cocok_perintah(teks_norm: str, kata_kunci: tuple[str, ...]) -> bool:
    if teks_norm in kata_kunci:
        return True
    return any(teks_norm.startswith(f"{k} ") for k in kata_kunci)


def _teks_menu(nama_bisnis: str) -> str:
    return (
        f"🍜 *Laksa — {nama_bisnis}*\n\n"
        "📊 *laporan* — analisis & rekomendasi hari ini\n"
        "❤️ *status* — skor kesehatan terakhir\n"
        "📈 *mingguan* — ringkasan 7 hari\n\n"
        "💰 Catat transaksi:\n"
        "• `masuk 50000 jualan`\n"
        "• `keluar 100000 beli stok`\n"
        "• `+50000` / `-25000`\n\n"
        "_Powered by Laksa 🌶️_"
    )


def _teks_status(id_bisnis: int) -> str:
    lap = repo.laporan_terakhir(id_bisnis)
    if not lap:
        return "Belum ada laporan. Ketik *laporan* untuk analisis baru."
    skor = int(lap.get("health_score") or 0)
    emoji = "🟢" if skor >= 70 else "🟡" if skor >= 40 else "🔴"
    waktu = lap.get("created_at")
    teks_waktu = waktu.strftime("%d %b %Y, %H:%M") if hasattr(waktu, "strftime") else str(waktu)[:16]
    return (
        f"🍜 *Status Keuangan Laksa*\n\n"
        f"{emoji} Skor kesehatan: *{skor}/100*\n"
        f"📅 Update: {teks_waktu}"
    )


def _teks_mingguan(id_bisnis: int) -> str:
    ringkas = repo.ringkasan_mingguan(id_bisnis)
    return (
        "📈 *Ringkasan 7 hari*\n"
        f"Pemasukan: Rp {float(ringkas['total_income']):,.0f}\n"
        f"Pengeluaran: Rp {float(ringkas['total_expense']):,.0f}\n"
        f"Arus bersih: Rp {float(ringkas['net_cashflow']):,.0f}\n"
        f"Jumlah transaksi: {ringkas.get('transaction_count', 0)}"
    )


def _jalankan_laporan_chat(id_bisnis: int, nomor_peer: str) -> dict[str, Any]:
    """Jalankan pipeline agen; balasan chat saja (tanpa kirim WA kedua dari Reporter)."""
    try:
        hasil = laksa_agent.invoke(
            {
                "business_id": id_bisnis,
                "trigger": "openclaw_chat",
                "tanggal_laporan": date.today(),
                "nomor_peer_whatsapp": nomor_peer,
                "lewati_wa_laporan": True,
                "errors": [],
            }
        )
    except Exception as exc:  # noqa: BLE001
        log_perintah.exception("laporan chat gagal: %s", exc)
        return {
            "handled": True,
            "reply": f"⚠️ Laporan gagal diproses: {exc}",
        }

    analisis = hasil.get("analysis_result") or {}
    if not analisis:
        return {
            "handled": True,
            "reply": "⚠️ Tidak ada data transaksi untuk dianalisis hari ini.",
            "agent_meta": {"business_id": id_bisnis},
        }

    teks = ReporterAgent._format_whatsapp(  # noqa: SLF001
        date.today(),
        Decimal(str(analisis.get("total_income", 0))),
        Decimal(str(analisis.get("total_expense", 0))),
        Decimal(str(analisis.get("net_cashflow", 0))),
        int(analisis.get("health_score", 50)),
        analisis.get("anomalies") or [],
        str(hasil.get("recommendations") or ""),
    )
    jalur_pdf = hasil.get("path_pdf") or ""
    if jalur_pdf:
        teks += "\n\n📄 PDF lengkap tersimpan di server."

    return {
        "handled": True,
        "reply": teks,
        "agent_meta": {
            "business_id": id_bisnis,
            "report_id": hasil.get("report_id"),
            "path_pdf": jalur_pdf,
            "errors": hasil.get("errors"),
        },
    }


def _coba_catat_transaksi(teks: str, id_bisnis: int) -> Optional[dict[str, Any]]:
    teks_bersih = teks.strip()
    cocok = POLA_TRANSAKSI.match(teks_bersih) or POLA_SINGKAT.match(teks_bersih)
    if not cocok:
        return None

    gr = cocok.groupdict()
    if "tanda" in gr and gr.get("tanda"):
        tipe = "income" if gr["tanda"] == "+" else "expense"
        jumlah_raw = gr.get("jumlah_raw") or ""
        keterangan = (gr.get("ket") or "chat whatsapp").strip()
    else:
        arah = (gr.get("arah") or "").lower()
        if arah in ("masuk", "pemasukan", "income", "in"):
            tipe = "income"
        else:
            tipe = "expense"
        jumlah_raw = gr.get("jumlah_raw") or ""
        keterangan = (gr.get("ket") or "chat whatsapp").strip()

    if not jumlah_raw:
        return {
            "handled": True,
            "reply": (
                "⚠️ Nominal kosong.\nContoh: `masuk 50000 jualan` atau `keluar 100000 beli stok`"
            ),
        }

    try:
        jumlah = _parse_nominal(jumlah_raw)
    except ValueError:
        return {
            "handled": True,
            "reply": f"⚠️ Nominal tidak dikenali: {jumlah_raw}",
        }

    if jumlah <= 0:
        return {"handled": True, "reply": "⚠️ Nominal harus lebih dari 0."}

    try:
        id_tx = repo.sisipkan_transaksi(
            business_id=id_bisnis,
            jumlah=jumlah,
            tipe=tipe,
            kategori="openclaw_chat",
            deskripsi=keterangan[:500],
            sumber="manual",
            tanggal=date.today(),
        )
    except Exception as exc:  # noqa: BLE001
        log_perintah.exception("gagal simpan transaksi chat: %s", exc)
        return {
            "handled": True,
            "reply": f"⚠️ Gagal menyimpan transaksi: {exc}",
        }

    label = "Pemasukan" if tipe == "income" else "Pengeluaran"
    return {
        "handled": True,
        "reply": (
            f"✅ *{label} tercatat*\n"
            f"💰 Rp {jumlah:,.0f}\n"
            f"📝 {keterangan}\n"
            f"🆔 Transaksi #{id_tx}\n\n"
            "Ketik *laporan* untuk analisis terbaru."
        ),
        "agent_meta": {"transaction_id": id_tx, "business_id": id_bisnis},
    }


def _parse_nominal(teks: str) -> Decimal:
    """Mengubah '50rb', '1.5jt', '50000' menjadi Decimal."""
    t = teks.strip().lower().replace(" ", "").replace(",", ".")
    pengali = Decimal("1")
    for sufiks, faktor in (
        ("juta", Decimal("1000000")),
        ("jt", Decimal("1000000")),
        ("ribu", Decimal("1000")),
        ("rb", Decimal("1000")),
        ("k", Decimal("1000")),
    ):
        if t.endswith(sufiks):
            t = t[: -len(sufiks)]
            pengali = faktor
            break
    try:
        return Decimal(t) * pengali
    except InvalidOperation as exc:
        raise ValueError(teks) from exc


def _belum_dipahami() -> dict[str, Any]:
    return {
        "handled": False,
        "reply": (
            "🍜 Saya belum paham perintahnya.\n"
            "Ketik *menu* untuk daftar perintah."
        ),
    }
