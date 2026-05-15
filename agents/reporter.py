"""Agen pelapor: database, WhatsApp, dan PDF."""

from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal
from typing import Any

from db import repo
from db.connection import dapatkan_koneksi
from sqlalchemy import text
from tools import openclaw_client, pdf_generator, twilio_client


def _format_tanggal_indonesia(tanggal: date) -> str:
    """Format tanggal ramah pembaca lokal."""
    bulan_id = {
        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember",
    }
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][
        tanggal.weekday()
    ]
    return f"{hari}, {tanggal.day} {bulan_id[tanggal.month]} {tanggal.year}"


class ReporterAgent:
    """Menyimpan laporan, mengirim WhatsApp, dan membuat PDF."""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        daftar_error = list(state.get("errors") or [])
        try:
            id_bisnis = int(state["business_id"])
            analisis = state.get("analysis_result") or {}
            rekomendasi = state.get("recommendations") or ""
            tanggal_laporan = state.get("tanggal_laporan") or date.today()

            total_masuk = Decimal(str(analisis.get("total_income", 0)))
            total_keluar = Decimal(str(analisis.get("total_expense", 0)))
            arus = Decimal(str(analisis.get("net_cashflow", 0)))
            skor = int(analisis.get("health_score", 50))
            anomali = analisis.get("anomalies") or []

            id_laporan = repo.sisipkan_laporan(
                business_id=id_bisnis,
                tipe_laporan="daily",
                mulai=tanggal_laporan,
                akhir=tanggal_laporan,
                skor=skor,
                total_masuk=total_masuk,
                total_keluar=total_keluar,
                arus_bersih=arus,
                anomali_json=json.dumps(anomali, ensure_ascii=False, default=str),
                rekomendasi=rekomendasi,
                whatsapp_terkirim=False,
            )

            for item in anomali:
                repo.sisipkan_anomali(
                    business_id=id_bisnis,
                    id_transaksi=item.get("transaction_id"),
                    tipe=str(item.get("type", "unknown")),
                    tingkat=str(item.get("severity", "medium")),
                    deskripsi=str(item.get("description", "")),
                )

            pesan = self._format_whatsapp(
                tanggal_laporan,
                total_masuk,
                total_keluar,
                arus,
                skor,
                anomali,
                rekomendasi,
            )
            wa_ok, pesan_error_wa = self._kirim_pesan_whatsapp_prioritas(state, pesan)
            for err in pesan_error_wa:
                daftar_error.append(err)

            direktori_pdf = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "reports",
            )
            nama_berkas = f"laporan_{id_bisnis}_{tanggal_laporan.isoformat()}.pdf"
            jalur_pdf = os.path.join(direktori_pdf, nama_berkas)
            pdf_generator.buat_pdf_laporan(
                jalur_pdf,
                "LAKSA — Laporan Harian",
                {
                    "business_id": id_bisnis,
                    "tanggal": tanggal_laporan.isoformat(),
                    "total_income": total_masuk,
                    "total_expense": total_keluar,
                    "net_cashflow": arus,
                    "health_score": skor,
                },
                rekomendasi,
            )

            # Memperbarui flag WhatsApp jika berhasil
            if wa_ok:
                with dapatkan_koneksi() as koneksi:
                    koneksi.execute(
                        text(
                            "UPDATE reports SET whatsapp_sent = TRUE WHERE id = :id_lap"
                        ),
                        {"id_lap": id_laporan},
                    )

            return {
                "report_id": id_laporan,
                "whatsapp_sent": wa_ok,
                "path_pdf": jalur_pdf,
                "errors": daftar_error,
            }
        except Exception as exc:  # noqa: BLE001
            daftar_error.append(f"reporter: {exc}")
            return {"whatsapp_sent": False, "errors": daftar_error}

    @staticmethod
    def _kirim_pesan_whatsapp_prioritas(
        state: dict[str, Any],
        teks_pesan: str,
    ) -> tuple[bool, list[str]]:
        """
        Utama: OpenClaw gateway (jika OPENCLAW_GATEWAY_URL di-set).
        Fallback: Twilio bila TWILIO_FALLBACK_ONLY=true (default) dan OpenClaw gagal.
        Tanpa gateway: hanya Twilio seperti sebelumnya.
        """
        daftar_pesan: list[str] = []
        nomor_peer = (
            (state.get("nomor_peer_whatsapp") or "").strip()
            or openclaw_client.tentukan_nomor_peer_dari_env()
        )
        url_gateway = os.getenv("OPENCLAW_GATEWAY_URL", "").strip()
        izinkan_fallback_twilio = os.getenv("TWILIO_FALLBACK_ONLY", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        if url_gateway:
            if openclaw_client.kirim_whatsapp_lewat_openclaw(nomor_peer, teks_pesan):
                return True, daftar_pesan
            daftar_pesan.append("openclaw: gagal kirim ke gateway")
            if not izinkan_fallback_twilio:
                return False, daftar_pesan

        hasil_twilio = twilio_client.kirim_whatsapp(teks_pesan)
        terkirim = bool(hasil_twilio.get("sent"))
        if not terkirim and hasil_twilio.get("error"):
            daftar_pesan.append(f"whatsapp_twilio: {hasil_twilio.get('error')}")
        return terkirim, daftar_pesan

    @staticmethod
    def _format_whatsapp(
        tanggal: date,
        total_masuk: Decimal,
        total_keluar: Decimal,
        arus: Decimal,
        skor: int,
        anomali: list[dict[str, Any]],
        rekomendasi: str,
    ) -> str:
        tanda = "+" if arus >= 0 else ""
        garis_anomali = ""
        if anomali:
            garis_anomali = "\n\n⚠️ *PERINGATAN ANOMALI*\n"
            garis_anomali += "\n".join(
                f"• {a.get('description', '')}" for a in anomali[:3]
            )
        rekomendasi_ringkas = rekomendasi.strip() or "(belum ada rekomendasi)"
        return (
            "🌶️ *LAKSA — Laporan Harian*\n"
            f"📅 {_format_tanggal_indonesia(tanggal)}\n\n"
            f"💰 Pemasukan: Rp {total_masuk:,.0f}\n"
            f"💸 Pengeluaran: Rp {total_keluar:,.0f}\n"
            f"📊 Arus Kas: {tanda}Rp {arus:,.0f}\n\n"
            f"❤️ Skor Kesehatan: {skor}/100"
            f"{garis_anomali}\n\n"
            "💡 *Rekomendasi:*\n"
            f"{rekomendasi_ringkas}\n\n"
            "_Powered by Laksa AI Agent 🍜_"
        )
