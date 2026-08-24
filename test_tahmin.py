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


class TestKrediKartiFinansmani(unittest.TestCase):
    """
    Kredi kartı finansman senaryosu Reel Değer'den BURAYA taşındı.

    Kart borcu zaten burada modelleniyordu (canlı bakiye + ödeme oranı + aylık ödeme
    sütunu); yalnız faiz eksikti. Aynı kart borcunu iki sekmede göstermek kural 5'e
    (sekmeler arası veri tekrarı yok) aykırıydı.
    """

    @staticmethod
    def _v(**kw):
        args = {"baslangic_ay": "2026-08", "baslangic_nakit": 1_000_000.0,
                "baz_ciro": 3_000_000.0, "marj_yuzde": 18.0, "sabit_gider": 400_000.0,
                "ufuk_ay": 6, "kart_borcu_acik": 100_000.0}
        args.update(kw)
        return TahminVarsayim(**args)

    def test_tam_odemede_finansman_maliyeti_yok(self):
        t = build_tahmin(self._v(kart_borcu_odeme_yuzde=100.0, kart_aylik_faiz_yuzde=4.0))
        self.assertAlmostEqual(t.toplam_kart_finansman, 0.0, places=2)
        self.assertAlmostEqual(t.kalan_kart_borcu, 0.0, places=2)
        self.assertAlmostEqual(t.toplam_kart_borcu_odeme, 100_000.0, places=2)

    def test_kismi_odemede_taşinan_borca_faiz_isler(self):
        t = build_tahmin(self._v(kart_borcu_odeme_yuzde=90.0, kart_aylik_faiz_yuzde=4.0))
        ilk = t.aylar[0]
        self.assertAlmostEqual(ilk.kart_borcu_odeme, 90_000.0, places=2)
        self.assertAlmostEqual(ilk.kart_finansman, 400.0, places=2)   # 10.000 × %4
        self.assertGreater(t.toplam_kart_finansman, 0.0)

    def test_faiz_sifirsa_eski_davranis(self):
        """Faiz girilmemişse hesap eskisi gibi: yalnız ödeme, maliyet yok."""
        t = build_tahmin(self._v(kart_borcu_odeme_yuzde=50.0, kart_aylik_faiz_yuzde=0.0))
        self.assertAlmostEqual(t.toplam_kart_finansman, 0.0, places=2)

    def test_faiz_nakdi_dolayli_azaltir(self):
        """Faiz kalan borcu büyütür → sonraki ayların ödemesi ve nakit çıkışı artar."""
        faizsiz = build_tahmin(self._v(kart_borcu_odeme_yuzde=50.0, kart_aylik_faiz_yuzde=0.0))
        faizli = build_tahmin(self._v(kart_borcu_odeme_yuzde=50.0, kart_aylik_faiz_yuzde=8.0))
        self.assertGreater(faizli.toplam_kart_borcu_odeme, faizsiz.toplam_kart_borcu_odeme)
        self.assertLess(faizli.son_nakit, faizsiz.son_nakit)

    def test_csv_faizi_tasir(self):
        t = build_tahmin(self._v(kart_borcu_odeme_yuzde=50.0, kart_aylik_faiz_yuzde=4.0))
        csv = tahmin_csv(t)
        self.assertIn("Kredi Kartı Aylık Faizi", csv)
        self.assertIn("Kart Finansman Maliyeti", csv)


class TestSonucOnceSoylenir(unittest.TestCase):
    """
    «Tamam 8'de düşüyor ama bana ne 8'den, sonunu söyle.»

    Özet ve uyarı, dip varsa YALNIZ dibi yazıyordu; 12 aylık projeksiyonun nereye
    vardığı hiçbir yerde geçmiyordu. Ayrıca bir ay düşüp toparlayan senaryo ile eksi
    kapatan senaryo aynı kırmızı şeritle aynı tavsiyeyi alıyordu — oysa yapılacak iş
    farklı: biri köprü finansman, diğeri büyüme/marj/gider kararı.
    """

    _ORTAK = {"baslangic_ay": "2026-07", "baslangic_nakit": 1_042_810.0,
              "baz_ciro": 3_234_753.0, "buyume_yuzde": 0.4, "marj_yuzde": 28.1,
              "sabit_gider": 356_949.0, "ufuk_ay": 12}

    def _t(self, **kw):
        return build_tahmin(TahminVarsayim(**{**self._ORTAK, **kw}))

    def test_bir_ay_dusup_toparlayan_kalici_degil(self):
        t = self._t(kart_borcu_acik=1_710_437.0, kart_borcu_odeme_yuzde=100.0)
        self.assertEqual(t.eksi_ay_sayisi, 1)
        self.assertFalse(t.kalici_eksi)
        self.assertGreater(t.son_nakit, 0)

    def test_dibin_sebebi_kart_odemesi_olarak_olculur(self):
        t = self._t(kart_borcu_acik=1_710_437.0, kart_borcu_odeme_yuzde=100.0)
        self.assertTrue(t.dip_sebebi_kart)
        # Kart borcu yoksa dip de yok, sebep iddiası da yok.
        self.assertFalse(self._t().dip_sebebi_kart)

    def test_eksi_kapatan_senaryo_kalici(self):
        t = self._t(sabit_gider=1_400_000.0)
        self.assertTrue(t.kalici_eksi)
        self.assertLess(t.son_nakit, 0)

    def test_dip_ayi_en_dusuk_ayla_ayni(self):
        t = self._t(kart_borcu_acik=1_710_437.0, kart_borcu_odeme_yuzde=100.0)
        self.assertEqual(t.dip_ayi.ay, t.en_dusuk_ay)
        self.assertAlmostEqual(t.dip_ayi.nakit, t.en_dusuk_nakit, places=2)

    def test_dipsiz_senaryoda_sayaclar_sifir(self):
        t = self._t()
        self.assertEqual(t.eksi_ay_sayisi, 0)
        self.assertFalse(t.kalici_eksi)


class TestBankaKredisiProjeksiyonda(unittest.TestCase):
    """
    Banka kredisi taksitleri NORMAL BEKLENTİYE girer.

    Canlı demoda kullanıcı haklı çıktı: «kredi kartını yazıyoruz ama bankadan
    çektiğimiz krediler yok — kaldı ki sistem kredi ödemelerini GÖRÜYOR». Taksit
    takvimi zaten çekiliyordu ama yalnız «en kötü ihtimal» tablosu kullanıyordu;
    manşet projeksiyon kredisiz, olduğundan iyimser çıkıyordu.
    """

    def _varsayim(self, **ek) -> TahminVarsayim:
        temel = dict(baslangic_ay="2026-07", baslangic_nakit=1_000_000.0,
                     baz_ciro=1_000_000.0, marj_yuzde=20.0, sabit_gider=100_000.0,
                     ufuk_ay=3)
        temel.update(ek)
        return TahminVarsayim(**temel)

    def test_taksit_nakitten_duser_kardan_dusmez(self) -> None:
        """Taksit bir yükümlülük ödemesidir: kârı değil nakdi etkiler (kartla aynı ilke)."""
        takvim = {"2026-08": 310_000.0, "2026-09": 310_000.0}
        krediili = build_tahmin(self._varsayim(kredi_takvimi=takvim))
        kredisiz = build_tahmin(self._varsayim())
        self.assertEqual(krediili.toplam_net, kredisiz.toplam_net)
        self.assertAlmostEqual(krediili.toplam_kredi_taksit, 620_000.0)
        self.assertAlmostEqual(kredisiz.son_nakit - krediili.son_nakit, 620_000.0)
        self.assertAlmostEqual(krediili.aylar[0].kredi_taksit, 310_000.0)
        self.assertAlmostEqual(krediili.aylar[2].kredi_taksit, 0.0)  # takvim bitti

    def test_taksitsiz_kredi_sabit_aylikla_modellenir(self) -> None:
        """Rotatif gibi taksit tanımı olmayan kredi: ölçülen aylık ortalama düşülür."""
        t = build_tahmin(self._varsayim(aylik_kredi_sabit=50_000.0))
        self.assertTrue(all(abs(a.kredi_taksit - 50_000.0) < 0.01 for a in t.aylar))
        self.assertAlmostEqual(t.toplam_kredi_taksit, 150_000.0)

    def test_kredi_yoksa_hicbir_iz_yok(self) -> None:
        """Kredisiz firmada sütun/KPI doğmasın diye toplam sıfır kalmalı (kural 6)."""
        t = build_tahmin(self._varsayim())
        self.assertEqual(t.toplam_kredi_taksit, 0.0)
        self.assertFalse(t.varsayim.kredi_var)
        self.assertNotIn("kredi taksidi", t.varsayim.ozet())

    def test_ozet_ve_csv_kredi_soyler(self) -> None:
        t = build_tahmin(self._varsayim(kredi_takvimi={"2026-08": 300_000.0}))
        self.assertIn("kredi taksidi", t.varsayim.ozet())
        csv = tahmin_csv(t)
        self.assertIn("Kredi Taksidi", csv)
        self.assertIn("TOPLAM;Kredi Taksitleri;300000,00", csv)

    def test_tab_taksit_penceresi_sabit_ve_anapara_ayrimi_var(self) -> None:
        """
        Kaynak bekçisi (import ETMEZ — PyQt gerekir):
        (a) taksit penceresi ufka bağlanamaz — kullanıcı «Doldur»dan sonra ufku
            36'ya çıkarabilir ve fetch tekrarlanmaz; dar pencere o ayları sessizce
            taksitsiz gösterirdi. Sabit 42 ay (azami ufuk 36 + 6).
        (b) runway'e ANAPARA takvimi seçilir (66 tarihsel gideri faizi zaten
            taşıyor) — tam taksit verilseydi faiz iki kez düşülürdü.
        """
        from pathlib import Path
        kaynak = (Path(__file__).parent / "ui" / "tabs" / "tahmin_tab.py").read_text(
            encoding="utf-8")
        self.assertIn("ay_ileri=42", kaynak)
        self.assertNotIn("ay_ileri=18", kaynak)
        self.assertIn("anapara_olculebilir(", kaynak)
        self.assertIn("anapara=True", kaynak)


class TestKrediTakvimYardimcilari(unittest.TestCase):
    def test_anapara_olculebilir(self) -> None:
        from domain.kredi import KrediTaksit, anapara_olculebilir
        dolu = [KrediTaksit(ay="2026-08", vade="2026-08-15", tutar=310_000.0,
                            anapara=250_000.0, faiz=60_000.0)]
        bos = [KrediTaksit(ay="2026-08", vade="2026-08-15", tutar=310_000.0)]
        self.assertTrue(anapara_olculebilir(dolu))
        self.assertFalse(anapara_olculebilir(bos))
        self.assertFalse(anapara_olculebilir([]))

    def test_iki_takvim_iki_tuketici(self) -> None:
        """Normal beklenti TAM taksit, runway ANAPARA — çift sayım kapısı burada."""
        from domain.kredi import KrediTaksit, kredi_takvimi_ay
        ts = [KrediTaksit(ay="2026-08", vade="2026-08-15", tutar=310_000.0,
                          anapara=250_000.0, faiz=60_000.0)]
        self.assertEqual(kredi_takvimi_ay(ts, ilk_ay="2026-08"), {"2026-08": 310_000.0})
        self.assertEqual(kredi_takvimi_ay(ts, ilk_ay="2026-08", anapara=True),
                         {"2026-08": 250_000.0})
