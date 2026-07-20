"""domain.bulgular kural motoru için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.bulgular import gercek_durum_bulgulari
from domain.gercek_durum import GercekDurum


def _gd(**kw) -> GercekDurum:
    # Varsayılan: sağlıklı, veri tam (kural tetiklemez)
    taban = dict(
        gercek_satis=100000.0, gercek_alis=70000.0,  # marj %30
        nakit_giren=50000.0, nakit_cikan=30000.0,     # net +20000
        nakit_mevcut=40000.0, alacak=20000.0, borc=10000.0,
        stok_kirilim_sayisi=3,
    )
    taban.update(kw)
    return GercekDurum(**taban)


class TestBulgular(unittest.TestCase):
    def _basliklar(self, gd) -> list[str]:
        return [b.baslik for b in gercek_durum_bulgulari(gd)]

    def test_nakit_eriyor_kritik(self):
        gd = _gd(nakit_giren=1000.0, nakit_cikan=5000.0)  # net -4000
        blist = gercek_durum_bulgulari(gd)
        self.assertEqual(blist[0].siddet, "kritik")
        self.assertEqual(blist[0].baslik, "Nakit eriyor")

    def test_nakit_pozitif_iyi(self):
        self.assertIn("Nakit akışı pozitif", self._basliklar(_gd()))

    def test_isletme_sermayesi_negatif(self):
        gd = _gd(nakit_mevcut=0.0, alacak=0.0, borc=50000.0)
        self.assertIn("İşletme sermayen negatif", self._basliklar(gd))

    def test_dusuk_marj_uyari(self):
        gd = _gd(gercek_satis=100000.0, gercek_alis=95000.0)  # marj %5
        self.assertIn("Al-sat marjın düşük", self._basliklar(gd))

    def test_borc_alacagi_asiyor(self):
        gd = _gd(borc=50000.0, alacak=1000.0)
        self.assertIn("Borçların alacaklarını aşıyor", self._basliklar(gd))

    def test_veri_eksik_bilgi(self):
        gd = _gd(stok_kirilim_sayisi=0)
        self.assertIn("Veri kısmi", self._basliklar(gd))

    def test_en_fazla_uc_ve_kritik_once(self):
        # Aynı anda çok sorun: kritik başta, en fazla 3
        gd = _gd(nakit_giren=0.0, nakit_cikan=9000.0,   # nakit eriyor (kritik)
                 nakit_mevcut=0.0, alacak=0.0, borc=80000.0,  # sermaye negatif (kritik) + borç>alacak
                 gercek_satis=100000.0, gercek_alis=98000.0)   # düşük marj
        blist = gercek_durum_bulgulari(gd)
        self.assertLessEqual(len(blist), 3)
        self.assertEqual(blist[0].siddet, "kritik")


if __name__ == "__main__":
    unittest.main()
