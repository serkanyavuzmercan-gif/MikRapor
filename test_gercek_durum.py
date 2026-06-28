"""
gercek_durum.build_gercek_durum için birim testleri (PyQt6 gerektirmez).
"""

from __future__ import annotations

import unittest

from gelir_tablosu import build_gelir_tablosu
from gercek_durum import build_gercek_durum, gercek_durum_csv, yuzde


def _stok_ozet():
    # tip=1 çıkış (satış), tip=0 giriş (alış); evraktip: 1=satış irs, 4=satış fat, 3=alış fat, 12=alış irs
    return [
        {"sth_tip": 1, "sth_evraktip": 1, "tutar": 37000.0, "miktar": 100, "adet": 10},  # satış irsaliye
        {"sth_tip": 1, "sth_evraktip": 4, "tutar": 5000.0, "miktar": 12, "adet": 2},      # satış fatura
        {"sth_tip": 0, "sth_evraktip": 3, "tutar": 30000.0, "miktar": 90, "adet": 8},     # alış fatura
        {"sth_tip": 0, "sth_evraktip": 12, "tutar": 2000.0, "miktar": 6, "adet": 1},      # alış irsaliye
    ]


def _nakit_ozet():
    return [{"giren": 40000.0, "cikan": 25000.0}]


def _bakiye_ozet():
    return [
        {"ana": "100", "bakiye": 5000.0},    # kasa (borç=varlık)
        {"ana": "102", "bakiye": 20000.0},   # banka
        {"ana": "103", "bakiye": -3000.0},   # verilen çek (kontra)
        {"ana": "120", "bakiye": 60000.0},   # alıcılar (alacağımız)
        {"ana": "320", "bakiye": -45000.0},  # satıcılar (borcumuz; alacak bakiyesi)
    ]


class TestGercekDurum(unittest.TestCase):
    def test_satis_bazi_sevk(self):
        gd = build_gercek_durum(stok_rows=_stok_ozet(), satis_bazi="sevk")
        self.assertAlmostEqual(gd.gercek_satis, 42000.0, places=2)   # 37000 + 5000
        self.assertAlmostEqual(gd.gercek_alis, 32000.0, places=2)    # 30000 + 2000
        self.assertAlmostEqual(gd.gercek_brut_kar, 10000.0, places=2)
        self.assertAlmostEqual(gd.gercek_brut_marj, 10000.0 / 42000.0 * 100, places=2)

    def test_satis_bazi_fatura(self):
        gd = build_gercek_durum(stok_rows=_stok_ozet(), satis_bazi="fatura")
        self.assertAlmostEqual(gd.gercek_satis, 5000.0, places=2)    # yalnız fatura
        self.assertAlmostEqual(gd.gercek_alis, 30000.0, places=2)    # yalnız alış fatura
        self.assertAlmostEqual(gd.satis_irsaliye, 37000.0, places=2)
        self.assertAlmostEqual(gd.satis_fatura, 5000.0, places=2)

    def test_nakit_ve_bakiye(self):
        gd = build_gercek_durum(
            stok_rows=_stok_ozet(), nakit_rows=_nakit_ozet(), bakiye_rows=_bakiye_ozet())
        self.assertAlmostEqual(gd.nakit_net, 15000.0, places=2)
        self.assertAlmostEqual(gd.nakit_mevcut, 22000.0, places=2)   # 5000+20000-3000
        self.assertAlmostEqual(gd.alacak, 60000.0, places=2)
        self.assertAlmostEqual(gd.borc, 45000.0, places=2)
        self.assertAlmostEqual(gd.net_isletme_sermayesi, 37000.0, places=2)  # 22000+60000-45000

    def test_resmi_karsilastirma(self):
        # Resmi GL: net satış 40000, SMM 35200 → brüt 4800 (%12); gerçek %23.8 → fark pozitif
        gl_rows = [
            {"hesap_kodu": "600.01", "borc": 0, "alacak": 40000},
            {"hesap_kodu": "621.01", "borc": 35200, "alacak": 0},
        ]
        gt = build_gelir_tablosu(gl_rows)
        gd = build_gercek_durum(stok_rows=_stok_ozet(), gelir_tablosu=gt, satis_bazi="sevk")
        self.assertIsNotNone(gd.resmi_brut_marj)
        self.assertAlmostEqual(gd.resmi_brut_marj, 12.0, places=1)
        self.assertGreater(gd.gercek_brut_marj, gd.resmi_brut_marj)
        self.assertIsNotNone(gd.marj_farki)
        self.assertGreater(gd.marj_farki, 0)
        self.assertIsNotNone(gd.gizlenen_brut)

    def test_trend_aylik(self):
        stok_aylik = [
            {"ay": "2025-01", "sth_tip": 1, "sth_evraktip": 1, "tutar": 10000.0},
            {"ay": "2025-01", "sth_tip": 0, "sth_evraktip": 3, "tutar": 7000.0},
            {"ay": "2025-02", "sth_tip": 1, "sth_evraktip": 4, "tutar": 12000.0},
        ]
        nakit_aylik = [
            {"ay": "2025-01", "giren": 8000.0, "cikan": 5000.0},
            {"ay": "2025-02", "giren": 9000.0, "cikan": 11000.0},
        ]
        gd = build_gercek_durum(stok_aylik=stok_aylik, nakit_aylik=nakit_aylik, satis_bazi="sevk")
        self.assertEqual([a.ay for a in gd.trend], ["2025-01", "2025-02"])
        ocak = gd.trend[0]
        self.assertAlmostEqual(ocak.satis, 10000.0, places=2)
        self.assertAlmostEqual(ocak.alis, 7000.0, places=2)
        self.assertAlmostEqual(ocak.brut, 3000.0, places=2)
        self.assertAlmostEqual(ocak.nakit_net, 3000.0, places=2)
        self.assertAlmostEqual(gd.trend[1].nakit_net, -2000.0, places=2)

    def test_csv_uretiliyor(self):
        gd = build_gercek_durum(
            stok_rows=_stok_ozet(), nakit_rows=_nakit_ozet(), bakiye_rows=_bakiye_ozet())
        csv = gercek_durum_csv(gd)
        self.assertIn("OPERASYONEL", csv)
        self.assertIn("Gerçek Brüt Marj", csv)
        self.assertIn("NAKİT", csv)

    def test_yuzde_format(self):
        self.assertEqual(yuzde(12.5), "%12,5")
        self.assertEqual(yuzde(-4.3), "%-4,3")

    def test_bos_veri_cokmez(self):
        gd = build_gercek_durum()
        self.assertEqual(gd.gercek_satis, 0.0)
        self.assertEqual(gd.gercek_brut_marj, 0.0)
        self.assertEqual(gd.trend, [])


if __name__ == "__main__":
    unittest.main()
