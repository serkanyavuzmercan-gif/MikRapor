"""Tahmin motoru testleri — projeksiyon, büyüme önerisi, varsayım önerisi, nakit uyarısı."""

import unittest

from domain.tahmin import (
    TahminVarsayim,
    _ay_ekle,
    aylik_buyume_oner,
    build_tahmin,
    ogrenme_penceresi_bas,
    oner_varsayim,
    tahmin_csv,
)


class TestOgrenmePenceresi(unittest.TestCase):
    """
    Öğrenme penceresi SEÇİLEN ARALIĞIN DIŞINA ÇIKAMAZ.

    Eskiden dar dönem seçildiğinde pencere geriye doğru 12 aya genişletiliyordu ve bu
    testler o davranışı sabitliyordu. Gerekçesi vardı (tek çeyrekte marj %49 çıkıp 12
    ayda ~%25'e oturuyor), ama kullanıcının seçmediği günlerin verisi rapora giriyordu.
    Kullanıcı bunu reddetti: «tarih aralığı kutsal, her şeyi o belirliyor».
    """

    def test_dar_donem_genisletilmez(self):
        """Q3 seçildiyse öğrenme de Q3'te kalır — 12 aya uzatılmaz."""
        self.assertEqual(ogrenme_penceresi_bas("2026-07-01", "2026-09-30"), "2026-07-01")

    def test_genis_donemde_son_12_ay(self):
        """Aralık 12 aydan genişse pencere son 12 ay: seçim dışına çıkmadan kısaltılır."""
        self.assertEqual(ogrenme_penceresi_bas("2024-01-01", "2026-09-30"), "2025-09-30")

    def test_tek_gunluk_donem(self):
        """Tek gün seçilirse pencere de o gün — 12 ay geriye kaçmaz."""
        self.assertEqual(ogrenme_penceresi_bas("2024-02-29", "2024-02-29"), "2024-02-29")

    def test_subat_29_tasmasi(self):
        """12 ay geri hesabı geçerli tarih üretmeli (29 Şubat olmayan yıl → 28)."""
        self.assertEqual(ogrenme_penceresi_bas("2020-01-01", "2024-02-29"), "2023-02-28")

    def test_bozuk_tarih_bas_dondurur(self):
        self.assertEqual(ogrenme_penceresi_bas("2026-07-01", "abc"), "2026-07-01")


class TestTahmin(unittest.TestCase):
    def test_projeksiyon_buyumesiz(self):
        v = TahminVarsayim(baslangic_ay="2026-06", baslangic_nakit=100000, baz_ciro=200000,
                           buyume_yuzde=0, marj_yuzde=25, sabit_gider=30000, ufuk_ay=3)
        t = build_tahmin(v)
        self.assertEqual(len(t.aylar), 3)
        a1 = t.aylar[0]
        self.assertEqual(a1.ay, "2026-07")
        self.assertAlmostEqual(a1.ciro, 200000, places=2)
        self.assertAlmostEqual(a1.brut_kar, 50000, places=2)   # 200k × 25%
        self.assertAlmostEqual(a1.net_kar, 20000, places=2)    # 50k − 30k
        self.assertAlmostEqual(a1.nakit, 120000, places=2)     # 100k + 20k
        self.assertAlmostEqual(t.aylar[2].nakit, 160000, places=2)  # +20k/ay
        self.assertAlmostEqual(t.toplam_ciro, 600000, places=2)
        self.assertAlmostEqual(t.son_nakit, 160000, places=2)

    def test_projeksiyon_buyumeli(self):
        v = TahminVarsayim(baslangic_ay="2026-06", baslangic_nakit=0, baz_ciro=100000,
                           buyume_yuzde=10, marj_yuzde=20, sabit_gider=0, ufuk_ay=2)
        t = build_tahmin(v)
        self.assertAlmostEqual(t.aylar[0].ciro, 110000, places=2)   # ×1.1
        self.assertAlmostEqual(t.aylar[1].ciro, 121000, places=2)   # ×1.1^2

    def test_nakit_eksiye_duser(self):
        v = TahminVarsayim(baslangic_ay="2026-06", baslangic_nakit=10000, baz_ciro=50000,
                           buyume_yuzde=0, marj_yuzde=10, sabit_gider=20000, ufuk_ay=3)
        t = build_tahmin(v)
        # net = 5000 − 20000 = −15000/ay → nakit 10k→−5k→−20k→−35k
        self.assertLess(t.en_dusuk_nakit, 0)
        self.assertEqual(t.en_dusuk_ay, t.aylar[-1].ay)

    def test_acik_kart_borcu_nakde_etki_eder_kara_degil(self):
        v = TahminVarsayim(
            baslangic_ay="2026-06", baslangic_nakit=100_000, baz_ciro=100_000,
            marj_yuzde=20, sabit_gider=10_000, kart_borcu_acik=100_000,
            kart_borcu_odeme_yuzde=25, ufuk_ay=3,
        )
        t = build_tahmin(v)
        # İşletme net kârı 10k/aydır; kart borcu nakit çıkışıdır, kâr değildir.
        self.assertAlmostEqual(t.aylar[0].net_kar, 10_000.0, places=2)
        self.assertAlmostEqual(t.aylar[0].kart_borcu_odeme, 25_000.0, places=2)
        self.assertAlmostEqual(t.aylar[0].net_nakit, -15_000.0, places=2)
        self.assertAlmostEqual(t.aylar[0].nakit, 85_000.0, places=2)
        self.assertAlmostEqual(t.toplam_kart_borcu_odeme, 57_812.5, places=2)
        self.assertAlmostEqual(t.kalan_kart_borcu, 42_187.5, places=2)
        self.assertAlmostEqual(t.toplam_net, 30_000.0, places=2)
        self.assertAlmostEqual(t.toplam_net_nakit, -27_812.5, places=2)

    def test_aylik_buyume_oner(self):
        self.assertAlmostEqual(aylik_buyume_oner([100, 110, 121]), 10.0, places=1)
        self.assertEqual(aylik_buyume_oner([100]), 0.0)
        self.assertEqual(aylik_buyume_oner([]), 0.0)
        self.assertLessEqual(aylik_buyume_oner([1, 1000000]), 20.0)   # üst sınır
        self.assertGreaterEqual(aylik_buyume_oner([1000000, 1]), -15.0)  # alt sınır

    def test_oner_varsayim(self):
        v = oner_varsayim(satis_serisi=[90000, 100000, 110000], brut_marj_yuzde=22.5,
                          baslangic_nakit=500000, aylik_sabit_gider=40000,
                          baslangic_ay="2026-06", ufuk_ay=12)
        self.assertAlmostEqual(v.baz_ciro, 100000, places=2)  # son 3 ay ort
        self.assertAlmostEqual(v.marj_yuzde, 22.5, places=2)
        self.assertAlmostEqual(v.baslangic_nakit, 500000, places=2)
        self.assertEqual(v.ufuk_ay, 12)
        self.assertGreater(v.buyume_yuzde, 0)  # artan seri

    def test_oner_varsayim_negatif_gider_sifirlanir(self):
        v = oner_varsayim(satis_serisi=[100000], brut_marj_yuzde=20, baslangic_nakit=0,
                          aylik_sabit_gider=-5000, baslangic_ay="2026-06")
        self.assertAlmostEqual(v.sabit_gider, 0.0, places=2)

    def test_ay_ekle(self):
        self.assertEqual(_ay_ekle("2026-06", 1), "2026-07")
        self.assertEqual(_ay_ekle("2026-11", 2), "2027-01")
        self.assertEqual(_ay_ekle("2026-12", 1), "2027-01")

    def test_csv(self):
        v = TahminVarsayim(baslangic_ay="2026-06", baz_ciro=100000, marj_yuzde=20, ufuk_ay=2)
        csv = tahmin_csv(build_tahmin(v))
        self.assertIn("VARSAYIM", csv)
        self.assertIn("PROJEKSİYON", csv)
        self.assertIn("Kart Borcu Ödemesi", csv)
        self.assertIn("Dönem Sonu Nakit", csv)


if __name__ == "__main__":
    unittest.main()
