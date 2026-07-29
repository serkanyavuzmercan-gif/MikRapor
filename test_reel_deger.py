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
    basabas_vade_farki,
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


def _analiz(parcalar, *, oran=45.0, vade_kaynagi="vade"):
    ta = TahsilatAlacak(acik_vade_parcalari=parcalar)
    ta.vade_kaynagi = vade_kaynagi
    return build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=oran))


class TestVadeMakasi(unittest.TestCase):
    """Tahsil günü ile ödeme günü arasındaki makas, kendi kesenden finanse edilen süredir."""

    def test_makas_aleyhte_hesaplanir(self):
        a = _analiz([AcikVadeParcasi("customer", 90, 1_000_000, "M1", "MUSTERI"),
                     AcikVadeParcasi("supplier", 30, 600_000, "S1", "SATICI")])
        self.assertAlmostEqual(a.makas_gun, 60.0, places=1)
        self.assertTrue(a.makas_var)
        self.assertFalse(a.makas_lehte)

    def test_makas_lehte_olabilir(self):
        """Tedarikçiye geç ödeyip müşteriden erken tahsil eden firma finanse EDİLİYOR."""
        a = _analiz([AcikVadeParcasi("customer", 15, 800_000, "M1", "MUSTERI"),
                     AcikVadeParcasi("supplier", 75, 800_000, "S1", "SATICI")])
        self.assertLess(a.makas_gun, 0.0)
        self.assertTrue(a.makas_lehte)

    def test_vade_kaydi_yoksa_makas_gosterilmez(self):
        """Kural 2: günler evrak tarihinden türetildiyse makas güvenilmez → gösterilmez."""
        a = _analiz([AcikVadeParcasi("customer", 90, 1_000_000, "M1", "MUSTERI"),
                     AcikVadeParcasi("supplier", 30, 600_000, "S1", "SATICI")],
                    vade_kaynagi="tarih")
        self.assertFalse(a.gun_olculdu)
        self.assertFalse(a.makas_var)

    def test_tedarikci_kredisi_olmayan_firma_makasi_gorur(self):
        """
        Yazılım/hizmet firması: müşteriye 60 gün vade, maliyeti peşin maaş, cari borç yok.

        «Hem alacak hem borç olsun» şartı bu firmayı tam da en geniş makasa sahipken
        ekrandan siliyordu; makasın parasal karşılığı da min(alacak,borç) ile
        hesaplanınca 3M'lik yükü 20 bin TL'lik kırtasiye faturasına indiriyordu.
        """
        a = _analiz([AcikVadeParcasi("customer", 60, 3_000_000, "K1", "KURUMSAL"),
                     AcikVadeParcasi("supplier", 0, 0.0, "S1", "YOK")])
        self.assertTrue(a.makas_var, "tedarikçi kredisi olmayan firmada makas gizlenmiş")
        self.assertTrue(a.tedarikci_kredisi_yok)
        self.assertAlmostEqual(a.makas_gun, 60.0, places=1)
        # Gerçek yük alacak tarafındaki erimededir; makas ayrı bir tutar uydurmaz.
        self.assertGreater(a.alacak.vade_etkisi, 100_000)

    def test_pesin_calisan_firmada_makas_gosterilmez(self):
        """Peşin alıp peşin satan firma (market/lokanta): vade riski yok, makas «—»."""
        a = _analiz([AcikVadeParcasi("customer", 0, 500_000, "M1", "PESIN MUSTERI"),
                     AcikVadeParcasi("supplier", 0, 300_000, "S1", "PESIN SATICI")])
        self.assertFalse(a.makas_var)
        self.assertAlmostEqual(a.makas_gun, 0.0, places=1)


class TestBasabasVadeFarki(unittest.TestCase):
    """İskonto oranını «vadeli satarken fiyata kaç puan ekle» tavsiyesine çevirir."""

    def test_peşin_satista_fark_gerekmez(self):
        self.assertEqual(basabas_vade_farki(0, 45), 0.0)

    def test_vade_uzadikca_gereken_fark_artar(self):
        d30 = basabas_vade_farki(30, 45)
        d90 = basabas_vade_farki(90, 45)
        d180 = basabas_vade_farki(180, 45)
        self.assertLess(d30, d90)
        self.assertLess(d90, d180)

    def test_90_gun_45_oranla_yaklasik_yuzde_10(self):
        self.assertAlmostEqual(basabas_vade_farki(90, 45), 9.59, places=1)

    def test_iskonto_dene_iskontonun_tersidir(self):
        """Başabaş fark, bugünkü değeri nominale geri götüren çarpandır."""
        pv = bugunku_deger(100_000, 90, 45)
        carpan = 1.0 + basabas_vade_farki(90, 45) / 100.0
        self.assertAlmostEqual(pv * carpan, 100_000, places=0)

    def test_oran_sifirsa_fark_yok(self):
        self.assertEqual(basabas_vade_farki(90, 0), 0.0)


class TestCariErimesi(unittest.TestCase):
    """
    Sıra BAKİYEYE değil ERİMEYE göre — Alacak & Borç'taki «en çok alacak» listesinin
    tekrarı olmasın (kural 5) ve rakamın arkası gösterilebilsin (kural 3c).
    """

    def test_buyuk_ama_hizli_odeyen_ustte_olmaz(self):
        a = _analiz([
            AcikVadeParcasi("customer", 15, 1_000_000, "M2", "BUYUK HIZLI"),
            AcikVadeParcasi("customer", 120, 500_000, "M1", "KUCUK YAVAS"),
        ])
        sira = [c.unvan for c in a.top_alacak_erime]
        self.assertEqual(sira[0], "KUCUK YAVAS",
                         "sıralama bakiyeye göre yapılmış — erimeye göre olmalı")

    def test_ayni_cari_parcalari_birlestirilir(self):
        a = _analiz([
            AcikVadeParcasi("customer", 30, 100_000, "M1", "MUSTERI"),
            AcikVadeParcasi("customer", 90, 300_000, "M1", "MUSTERI"),
        ])
        self.assertEqual(len(a.top_alacak_erime), 1)
        c = a.top_alacak_erime[0]
        self.assertAlmostEqual(c.nominal, 400_000, places=2)
        self.assertAlmostEqual(c.agirlikli_gun, (30 * 100_000 + 90 * 300_000) / 400_000, places=1)

    def test_cari_erimeleri_toplami_ozetle_tutar(self):
        parcalar = [
            AcikVadeParcasi("customer", 30, 100_000, "M1", "A"),
            AcikVadeParcasi("customer", 90, 300_000, "M2", "B"),
            AcikVadeParcasi("customer", 200, 250_000, "M3", "C"),
        ]
        a = _analiz(parcalar)
        toplam = sum(c.vade_etkisi for c in a.top_alacak_erime)
        self.assertAlmostEqual(toplam, a.alacak.vade_etkisi, places=2)

    def test_erimesi_olmayan_listelenmez(self):
        a = _analiz([AcikVadeParcasi("customer", 0, 500_000, "M1", "PESIN")])
        self.assertEqual(a.top_alacak_erime, [])


class TestCsvYeniBolumler(unittest.TestCase):
    def test_csv_makas_basabas_ve_cari_icerir(self):
        a = _analiz([AcikVadeParcasi("customer", 90, 1_000_000, "M1", "MUSTERI A"),
                     AcikVadeParcasi("supplier", 30, 600_000, "S1", "SATICI B")])
        csv = reel_deger_csv(a)
        self.assertIn("VADE MAKASI;Makas (gün)", csv)
        self.assertIn("VADE MAKASI;Yön;aleyhte", csv)
        self.assertIn("BAŞABAŞ VADE FARKI;90 gün (%)", csv)
        self.assertIn("EN ÇOK ERİTEN MÜŞTERİ;MUSTERI A", csv)
        self.assertIn("EN ÇOK KAZANDIRAN SATICI;SATICI B", csv)

    def test_vade_olculmediyse_csv_sebebini_yazar(self):
        a = _analiz([AcikVadeParcasi("customer", 90, 1_000_000, "M1", "M"),
                     AcikVadeParcasi("supplier", 30, 600_000, "S1", "S")],
                    vade_kaynagi="tarih")
        self.assertIn("VADE MAKASI;Ölçülemedi", reel_deger_csv(a))


if __name__ == "__main__":
    unittest.main()
