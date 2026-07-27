"""domain.kredi — taksit derleme, ay takvimi, özet testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.kredi import (
    kredi_karti_borclarini_derle,
    kredi_karti_odeme_takvimi,
    kredi_odemelerini_derle,
    kredi_ozet,
    kredi_takvimi_ay,
    taksitleri_derle,
)


def _row(vade, tutar, anapara=0.0, faiz=0.0, banka="VB"):
    return {"ay": vade[:7], "vade": vade, "tutar": tutar,
            "anapara": anapara, "faiz": faiz, "banka": banka}


class TestKredi(unittest.TestCase):
    def test_acik_kart_borcu_odeme_takvimi(self):
        borclar = kredi_karti_borclarini_derle([
            {"hesap": "300.02.0002", "hesap_ad": "Vakıfbank Kredi Kartı", "borc": 80_000},
            {"hesap": "300.02.0001", "hesap_ad": "Akbank Kredi Kartı", "borc": 20_000},
            {"hesap": "300.02.0003", "borc": 0},
        ])
        self.assertEqual(len(borclar), 2)
        self.assertEqual(borclar[0].hesap, "300.02.0002")
        takvim = kredi_karti_odeme_takvimi(
            borclar, baslangic_ay="2026-06", odeme_yuzde=25, ufuk_ay=3)
        self.assertAlmostEqual(takvim["2026-07"], 25_000.0, places=2)
        self.assertAlmostEqual(takvim["2026-08"], 18_750.0, places=2)
        self.assertAlmostEqual(takvim["2026-09"], 14_062.5, places=2)

    def test_donem_odemelerini_derle_ve_sirala(self):
        odemeler = kredi_odemelerini_derle([
            {"tarih": "2026-06-15", "hesap": "300.01.0004",
             "hesap_ad": "Vakıfbank Kredi", "tutar": 104478.90},
            {"tarih": "2026-04-03", "hesap": "300.01.0001",
             "hesap_ad": "Akbank Kredi", "tutar": 130869.10},
            {"tarih": "2026-05-01", "hesap": "300.01.0002", "tutar": 0},
        ])
        self.assertEqual(len(odemeler), 2)
        self.assertEqual(odemeler[0].tarih, "2026-04-03")
        self.assertEqual(odemeler[0].hesap_ad, "Akbank Kredi")
        self.assertAlmostEqual(odemeler[1].tutar, 104478.90, places=2)

    def test_derle_ve_sirala(self):
        t = taksitleri_derle([
            _row("2026-11-15", 100000, 80000, 20000),
            _row("2026-10-15", 100000, 82000, 18000),
            _row("2026-12-15", 0.0),  # tutarsız — atlanır
        ])
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0].vade, "2026-10-15")  # sıralı
        self.assertAlmostEqual(t[0].anapara, 82000, places=2)

    def test_takvim_ay_toplar(self):
        t = taksitleri_derle([
            _row("2026-10-15", 100000), _row("2026-10-28", 50000),
            _row("2026-11-15", 90000),
        ])
        tk = kredi_takvimi_ay(t, ilk_ay="2026-10")
        self.assertAlmostEqual(tk["2026-10"], 150000, places=2)
        self.assertAlmostEqual(tk["2026-11"], 90000, places=2)

    def test_gecikmis_ilk_aya_yigilir(self):
        # Vadesi ilk_ay'dan önce (gecikmiş, ödenmemiş) → ilk_ay'a taşınır.
        t = taksitleri_derle([_row("2026-08-15", 40000), _row("2026-11-15", 60000)])
        tk = kredi_takvimi_ay(t, ilk_ay="2026-10")
        self.assertAlmostEqual(tk["2026-10"], 40000, places=2)  # gecikmiş buraya
        self.assertAlmostEqual(tk["2026-11"], 60000, places=2)

    def test_ozet_toplam_ve_gecikmis(self):
        t = taksitleri_derle([
            _row("2026-08-15", 40000, 35000, 5000),
            _row("2026-11-15", 60000, 52000, 8000),
        ])
        oz = kredi_ozet(t, bugun_ay="2026-10", en_fazla=8)
        self.assertAlmostEqual(oz.toplam, 100000, places=2)
        self.assertAlmostEqual(oz.toplam_faiz, 13000, places=2)
        self.assertAlmostEqual(oz.gecikmis_tutar, 40000, places=2)
        self.assertEqual(oz.gecikmis_adet, 1)


if __name__ == "__main__":
    unittest.main()
