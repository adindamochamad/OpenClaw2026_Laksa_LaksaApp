"""Agen penasihat: satu-satunya pemanggil LLM (Claude)."""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic


class AdvisorAgent:
    """Menghasilkan rekomendasi praktis berbahasa Indonesia."""

    SYSTEM_PROMPT = """Kamu adalah konsultan keuangan UMKM Indonesia yang berpengalaman.
Berikan rekomendasi yang praktis, actionable, dan dalam Bahasa Indonesia
yang mudah dipahami oleh pemilik warung atau toko kecil.

Rules:
- Gunakan bahasa yang hangat dan tidak menghakimi
- Berikan maksimal 3 rekomendasi konkret
- Setiap rekomendasi harus bisa dilakukan hari ini atau minggu ini
- Sertakan angka spesifik jika relevan
- Jangan gunakan jargon akuntansi yang rumit
- Format: poin-poin singkat, bukan paragraf panjang"""

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        daftar_error = list(state.get("errors") or [])
        try:
            analisis = state.get("analysis_result") or {}
            api_key = os.getenv("ANTHROPIC_API_KEY")
            nama_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

            if not api_key:
                teks = self._cadangan_tanpa_api(analisis)
                return {"recommendations": teks, "errors": daftar_error}

            klien = Anthropic(api_key=api_key)
            user_content = (
                "Berikut ringkasan analitik (JSON). Buat rekomendasi sesuai aturan sistem.\n"
                + json.dumps(analisis, ensure_ascii=False, default=str)
            )
            respons = klien.messages.create(
                model=nama_model,
                max_tokens=700,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            blok_teks = ""
            for blok in respons.content:
                if blok.type == "text":
                    blok_teks += blok.text
            teks = (blok_teks or "").strip() or self._cadangan_tanpa_api(analisis)
            return {"recommendations": teks, "errors": daftar_error}
        except Exception as exc:  # noqa: BLE001
            daftar_error.append(f"advisor: {exc}")
            teks_cadangan = self._cadangan_tanpa_api(state.get("analysis_result") or {})
            return {"recommendations": teks_cadangan, "errors": daftar_error}

    @staticmethod
    def _cadangan_tanpa_api(analisis: dict[str, Any]) -> str:
        """Rekomendasi deterministik jika API tidak tersedia atau gagal."""
        skor = int(analisis.get("health_score", 50))
        arus = analisis.get("net_cashflow", 0)
        try:
            arus_angka = float(arus)
        except (TypeError, ValueError):
            arus_angka = 0.0
        baris = [
            "1. Catat pemasukan dan pengeluaran harian secara konsisten agar laporan tetap akurat.",
            f"2. Pantau arus kas hari ini (nilai bersih sekitar Rp {arus_angka:,.0f}) dan tunda pengeluaran non-penting bila perlu.",
            f"3. Jaga ritme operasional mingguan; skor kesehatan terakhir sekitar {skor}/100 — fokus pada efisiensi stok.",
        ]
        return "\n".join(baris)
