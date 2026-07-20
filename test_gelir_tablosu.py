"""domain.gelir_tablosu build_gelir_tablosu için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.gelir_tablosu import build_gelir_tablosu


class TestGelirTablosu(unittest.TestCase):
    def test_faaliyet_ve_finansman_gideri(self):
        # tutar = alacak − borç → gider hesapları negatif çıkar
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0, "alacak": 100000},
            {"hesap_kodu": "631", "borc": 15000, "alacak": 0},   # 63 pazarlama gideri
            {"hesap_kodu": "632", "borc": 5000, "alacak": 0},    # 63 genel yönetim
            {"hesap_kodu": "660", "borc": 4000, "alacak": 0},    # 66 finansman
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertAlmostEqual(gt.faaliyet_gideri, -20000.0, places=2)  # 63 toplam
        self.assertAlmostEqual(gt.finansman_gideri, -4000.0, places=2)  # 66 toplam

    def test_gider_yoksa_sifir(self):
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0, "alacak": 50000},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertEqual(gt.faaliyet_gideri, 0.0)
        self.assertEqual(gt.finansman_gideri, 0.0)


if __name__ == "__main__":
    unittest.main()
