"""
Skrip seed: bisnis contoh + impor CSV seed_transactions.csv.
Jalankan dari root proyek: python db/seed.py
"""

import csv
import os
import sys
from datetime import date
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import text

# Pastikan root proyek ada di path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import dapatkan_koneksi  # noqa: E402

load_dotenv()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "seed_transactions.csv")


def jalankan_seed():
    """Memasukkan bisnis id=1 (jika belum) dan transaksi dari CSV."""
    with dapatkan_koneksi() as koneksi:
        baris_bisnis = koneksi.execute(
            text("SELECT id FROM businesses WHERE id = 1 LIMIT 1")
        ).fetchone()
        if not baris_bisnis:
            koneksi.execute(
                text(
                    """
                    INSERT INTO businesses (id, name, owner_name, phone, business_type)
                    VALUES (1, 'Warung Laksa Demo', 'Budi', '+6280000000001', 'warung')
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        owner_name = VALUES(owner_name),
                        phone = VALUES(phone),
                        business_type = VALUES(business_type)
                    """
                )
            )

        koneksi.execute(text("DELETE FROM transactions WHERE business_id = 1"))

        if not os.path.isfile(CSV_PATH):
            raise FileNotFoundError(f"File tidak ditemukan: {CSV_PATH}")

        with open(CSV_PATH, newline="", encoding="utf-8") as berkas_csv:
            pembaca = csv.DictReader(berkas_csv)
            for baris in pembaca:
                tanggal = date.fromisoformat(baris["date"].strip())
                jumlah = Decimal(baris["amount"].strip())
                koneksi.execute(
                    text(
                        """
                        INSERT INTO transactions
                        (business_id, amount, type, category, description, source, transaction_date)
                        VALUES (:bid, :amount, :tipe, :category, :description, 'csv_upload', :tgl)
                        """
                    ),
                    {
                        "bid": 1,
                        "amount": str(jumlah),
                        "tipe": baris["type"].strip(),
                        "category": baris.get("category", "").strip() or None,
                        "description": baris.get("description", "").strip() or None,
                        "tgl": tanggal.isoformat(),
                    },
                )

    print("Seed selesai: business_id=1 dan transaksi dari seed_transactions.csv.")


if __name__ == "__main__":
    jalankan_seed()
