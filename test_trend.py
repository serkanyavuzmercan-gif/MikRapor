"""Trend & Oranlar — domain birim testleri."""

from __future__ import annotations

import unittest

from domain.gercek_durum import AyTrend
from domain.mizan_bilanco import build_bilanco
from domain.trend import build_finansal_oranlar, build_trend, trend_csv


class TestTrend(unittest.TestCase):
    def test_oranlar_bilanco(self) -> None:
        b = build_bilanco([
            {"hesap_kodu": "100", "borc": 5000.0, "alacak": 0.0},
            {"hesap_kodu": "120", "borc": 15000.0, "alacak": 0.0},
            {"hesap_kodu": "150", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 20000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 10000.0},
        ], asof="2026-06-30")
        oranlar, ozet = build_finansal_oranlar(b)
        self.assertGreater(ozet["donen"], 0)
        self.assertGreater(ozet["kvyk"], 0)
        cari = next(o for o in oranlar if o.kod == "cari")
        self.assertIsNotNone(cari.deger)
        self.assertAlmostEqual(cari.deger or 0, ozet["donen"] / ozet["kvyk"], places=4)

    def test_build_trend_ve_csv(self) -> None:
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 8000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 4000.0},
        ], asof="2026-06-30")
        aylik = [
            AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000),
            AyTrend(ay="2026-02", satis=12000, alis=7000, nakit_giren=9000, nakit_cikan=6000),
        ]
        tr = build_trend(aylik=aylik, bilanco=b, bas="2026-01-01", bit="2026-06-30")
        self.assertEqual(tr.ay_sayisi, 2)
        self.assertEqual(tr.toplam_satis, 22000)
        self.assertTrue(tr.oranlar)
        csv = trend_csv(tr)
        self.assertIn("ORAN;", csv)
        self.assertIn("AYLIK;2026-01 Satış;", csv)


if __name__ == "__main__":
    unittest.main()
