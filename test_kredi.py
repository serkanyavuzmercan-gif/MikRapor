"""domain.kredi — taksit derleme, ay takvimi, özet testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.kredi import kredi_ozet, kredi_takvimi_ay, taksitleri_derle


def _row(vade, tutar, anapara=0.0, faiz=0.0, banka="VB"):
    return {"ay": vade[:7], "vade": vade, "tutar": tutar,
            "anapara": anapara, "faiz": faiz, "banka": banka}


class TestKredi(unittest.TestCase):
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
