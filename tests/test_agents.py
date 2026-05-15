from datetime import date

from tools import anomaly_detector


def test_deteksi_expense_spike():
    """Pengeluaran hari ini jauh di atas rata-rata memicu expense_spike."""
    transaksi = []
    for hari in range(8, 15):
        transaksi.append(
            {
                "id": hari,
                "amount": 300000,
                "type": "expense",
                "category": "stok",
                "date": f"2026-05-{hari:02d}",
            }
        )
    transaksi.append(
        {
            "id": 99,
            "amount": 850000,
            "type": "expense",
            "category": "lain",
            "date": "2026-05-15",
        }
    )
    hasil = anomaly_detector.deteksi_expense_spike(transaksi, date(2026, 5, 15))
    assert len(hasil) >= 1
    assert hasil[0]["type"] == "expense_spike"
