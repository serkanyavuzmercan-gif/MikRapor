"""Reel değer ve kart finansman senaryosu testleri."""

from __future__ import annotations

import unittest

from domain.reel_deger import (
    ReelDegerVarsayim,
    bugunku_deger,
    build_reel_deger_analizi,
    kart_finansmani_hesapla,
    reel_deger_csv,
)
from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak


class TestReelDeger(unittest.TestCase):
    def test_bugunku_deger_vadeyle_azalir(self):
        self.assertAlmostEqual(bugunku_deger(100_000, 0, 45), 100_000, places=2)
        self.assertLess(bugunku_deger(100_000, 90, 45), 100_000)

    def test_alacak_borc_reel_pozisyonu(self):
        ta = TahsilatAlacak(acik_vade_parcalari=[
            AcikVadeParcasi("customer", 90, 1_000_000),
            AcikVadeParcasi("supplier", 30, 400_000),
        ])
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        self.assertAlmostEqual(a.nominal_net_pozisyon, 600_000, places=2)
        self.assertLess(a.reel_net_pozisyon, a.nominal_net_pozisyon)
        self.assertGreater(a.alacak.vade_etkisi, a.borc.vade_etkisi)

    def test_kart_tam_odeme_faizsiz(self):
        k = kart_finansmani_hesapla(ReelDegerVarsayim(
            kart_borcu_acik=100_000, kart_odeme_yuzde=100, kart_aylik_faiz_yuzde=4,
        ))
        self.assertTrue(k.kapandi_mi)
        self.assertAlmostEqual(k.toplam_odeme, 100_000, places=2)
        self.assertAlmostEqual(k.toplam_finansman_maliyeti, 0.0, places=2)

    def test_kart_kismi_odeme_finansman_maliyeti_olusturur(self):
        k = kart_finansmani_hesapla(ReelDegerVarsayim(
            kart_borcu_acik=100_000, kart_odeme_yuzde=90, kart_aylik_faiz_yuzde=4,
        ))
        self.assertAlmostEqual(k.aylar[0].odeme, 90_000, places=2)
        self.assertAlmostEqual(k.aylar[0].finansman_maliyeti, 400, places=2)
        self.assertGreater(k.toplam_finansman_maliyeti, 0.0)
        self.assertGreater(k.toplam_odeme, 100_000)

    def test_csv(self):
        a = build_reel_deger_analizi(
            TahsilatAlacak(), ReelDegerVarsayim(kart_borcu_acik=100_000))
        self.assertIn("KART TAKVİMİ", reel_deger_csv(a))


if __name__ == "__main__":
    unittest.main()
