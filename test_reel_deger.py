"""
Reel Değer — vade etkisi testleri.

Kredi kartı senaryosu bu sekmeden ÇIKARILDI (Tahmin & Projeksiyon'a taşındı): buradaki
dört değişkenin üçü yalnız en alttaki kart tablosunu besliyordu ve panel bunu hiçbir
yerde söylemiyordu. Kart testleri test_tahmin.py'ye taşındı.
"""

from __future__ import annotations

import unittest

from domain.reel_deger import (
    ReelDegerVarsayim,
    bugunku_deger,
    build_reel_deger_analizi,
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

    def test_tek_degisken_kaldi(self):
        """Sekme tek soruyu cevaplıyor; kart alanları burada olmamalı."""
        alanlar = set(ReelDegerVarsayim().__dataclass_fields__)
        self.assertEqual(alanlar, {"yillik_iskonto_yuzde"})

    def test_csv_kart_icermez(self):
        csv = reel_deger_csv(build_reel_deger_analizi(TahsilatAlacak(), ReelDegerVarsayim()))
        self.assertNotIn("KART", csv)
        self.assertIn("Paranın yıllık maliyeti", csv)
        self.assertIn("NET;Vade etkisi", csv)


if __name__ == "__main__":
    unittest.main()
