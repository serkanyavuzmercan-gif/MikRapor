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

    def test_stoga_baglanan_para(self):
        """Alınan mal satılanın maliyetini aşıyorsa haber stok, marj sapması değil."""
        gd = _gd(gercek_alis=70000.0, resmi_smm=50000.0,     # 20.000 stoğa gitti
                 resmi_net_satis=100000.0, resmi_brut_kar=50000.0)
        self.assertIn("Para stoğa bağlandı", self._basliklar(gd))

    def test_stoktan_satis_bilgi(self):
        gd = _gd(gercek_alis=70000.0, resmi_smm=90000.0,     # 20.000 stoktan eridi
                 resmi_net_satis=100000.0, resmi_brut_kar=10000.0)
        self.assertIn("Stoktan satış yapıldı", self._basliklar(gd))

    def test_kucuk_stok_hareketi_haber_degil(self):
        gd = _gd(gercek_alis=70000.0, resmi_smm=69000.0,     # satışın %1'i
                 resmi_net_satis=100000.0, resmi_brut_kar=31000.0)
        basliklar = self._basliklar(gd)
        self.assertNotIn("Para stoğa bağlandı", basliklar)
        self.assertNotIn("Stoktan satış yapıldı", basliklar)

    def test_resmi_marj_saglikliysa_dusuk_marj_uyarisi_verilmez(self):
        """
        Canlı vaka: fiili marj %1,8, resmi %10,4 — sebep fiyatlama değil, stok.

        "Al-sat marjın düşük" demek yanlış alarmdı; kullanıcı fiyatlarını gözden
        geçirmeye değil, stoğuna bakmaya yönlendirilmeli.
        """
        gd = _gd(gercek_satis=132_872_858.87, gercek_alis=130_497_748.24,   # %1,8
                 resmi_brut_marj=10.35, resmi_smm=120_362_156.33,
                 resmi_net_satis=134_260_075.88, resmi_brut_kar=13_897_919.55)
        basliklar = self._basliklar(gd)
        self.assertNotIn("Al-sat marjın düşük", basliklar)
        self.assertIn("Para stoğa bağlandı", basliklar)

    def test_resmi_marj_da_dusukse_uyari_kalir(self):
        """Resmi marj da düşükse sorun gerçekten fiyatlamada."""
        gd = _gd(gercek_satis=100000.0, gercek_alis=95000.0,
                 resmi_brut_marj=4.0, resmi_smm=95000.0,
                 resmi_net_satis=100000.0, resmi_brut_kar=5000.0)
        self.assertIn("Al-sat marjın düşük", self._basliklar(gd))

    def test_marj_sapmasi_artik_uyari_degil(self):
        """Muhasebe zamanlaması usulsüzlük gibi okutulmamalı."""
        gd = _gd(gercek_satis=100000.0, gercek_alis=70000.0,
                 resmi_smm=50000.0, resmi_net_satis=100000.0, resmi_brut_kar=50000.0)
        self.assertNotIn("Resmi ve fiili marj ayrışıyor", self._basliklar(gd))

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
