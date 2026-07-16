"""
mizan_bilanco.build_bilanco için birim testleri (PyQt6 gerektirmez).
"""

from __future__ import annotations

import unittest

from domain.mizan_bilanco import ana_hesap, bilanco_html, build_bilanco, tl


def _dengeli_mizan():
    # Σborç = Σalacak = 14000 (çift kayıt)
    return [
        {"hesap_kodu": "100.01", "borc": 1000, "alacak": 0},      # Kasa
        {"hesap_kodu": "102.001", "borc": 5000, "alacak": 0},     # Bankalar
        {"hesap_kodu": "120.01.0014", "borc": 3000, "alacak": 0}, # Alıcılar
        {"hesap_kodu": "153.01", "borc": 2000, "alacak": 0},      # Ticari Mallar
        {"hesap_kodu": "257.01", "borc": 0, "alacak": 500},       # Birikmiş Amort (-)
        {"hesap_kodu": "320.01.0018", "borc": 0, "alacak": 3500}, # Satıcılar
        {"hesap_kodu": "300.01", "borc": 0, "alacak": 2000},      # Banka Kredisi
        {"hesap_kodu": "500.01", "borc": 0, "alacak": 3000},      # Sermaye
        {"hesap_kodu": "600.01", "borc": 0, "alacak": 5000},      # Yurtiçi Satış
        {"hesap_kodu": "620.01", "borc": 3000, "alacak": 0},      # SMM
        {"hesap_kodu": "900.01", "borc": 1500, "alacak": 0},      # nazım borç
        {"hesap_kodu": "900.02", "borc": 0, "alacak": 1500},      # nazım alacak (net 0)
    ]


class TestBilanco(unittest.TestCase):
    def test_ana_hesap(self):
        self.assertEqual(ana_hesap("320.01.0018"), "320")
        self.assertEqual(ana_hesap("102"), "102")
        self.assertEqual(ana_hesap(""), "")

    def test_tl_format(self):
        self.assertEqual(tl(1234567.8), "1.234.567,80")
        self.assertEqual(tl(-500), "-500,00")

    def test_denge(self):
        b = build_bilanco(_dengeli_mizan(), asof="2026-06-30")
        # Aktif = 1000+5000+3000+2000-500 = 10500
        self.assertAlmostEqual(b.aktif_toplam, 10500.0, places=2)
        # Pasif kaynak = 3500+2000+3000 = 8500 ; Dönem K/Z = 5000-3000 = 2000 ; toplam 10500
        self.assertAlmostEqual(b.donem_kz, 2000.0, places=2)
        self.assertAlmostEqual(b.pasif_toplam, 10500.0, places=2)
        self.assertAlmostEqual(b.fark, 0.0, places=2)
        self.assertTrue(b.dengede)

    def test_kontra_hesap_aktifi_azaltir(self):
        b = build_bilanco(_dengeli_mizan(), asof="2026-06-30")
        amort = [s for s in b.aktif if s.ana == "257"]
        self.assertEqual(len(amort), 1)
        self.assertLess(amort[0].tutar, 0)  # birikmiş amortisman negatif

    def test_nazim_net_sifir_dengeyi_bozmaz(self):
        b = build_bilanco(_dengeli_mizan(), asof="2026-06-30")
        self.assertAlmostEqual(b.digit_net.get("9", 0.0), 0.0, places=2)
        self.assertAlmostEqual(b.fark, 0.0, places=2)

    def test_html_uretiliyor(self):
        b = build_bilanco(_dengeli_mizan(), asof="2026-06-30")
        html = bilanco_html(b, firma="Test A.Ş.")
        self.assertIn("ANINDA BİLANÇO", html)
        self.assertIn("Test A.Ş.", html)
        self.assertIn("DENGEDE", html)
        self.assertIn("Bankalar", html)


if __name__ == "__main__":
    unittest.main()
