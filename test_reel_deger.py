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


def _analiz(parcalar, *, oran=45.0, dso=None, donem_gun=0, gecikmis=0.0):
    ta = TahsilatAlacak(acik_vade_parcalari=parcalar)
    ta.donem_gun = donem_gun
    ta.alacak_gecikmis = gecikmis
    if dso is not None:                      # dso bir property; akıştan türet
        ta.alacak_toplam = dso
        ta.donem_satis = float(donem_gun)
        ta.donem_gun = donem_gun
    return build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=oran))


class TestBasabasDsoyaCapalanir(unittest.TestCase):
    """
    Başabaş fark ÖLÇÜLEN TAHSİL SÜRESİNE (DSO) çapalanır, «vadeye kalan»a değil.

    Vade makası paneli KALDIRILDI: aynı soruyu Alacak & Borç sekmesi zaten dso/dpo ile
    doğru cevaplıyordu (kural 5, veri tekrarı yok) ve buradaki hesap iki «vadeye kalan»
    ortalamasının farkıydı — canlıda 17−18 = 1 gün, işareti de o sekmenin tersi.

    «Vadeye kalan» çapa olarak yanlıştı çünkü FIFO en eski faturayı kapatıyor: açık
    kalanlar en yeni faturalar oluyor ve tahsilat iyileştikçe rakam düşüyor. 90 gün
    vadeyle çalışan firmada %70 tahsilatta 20 güne iniyordu → %1,7 diyordu, doğrusu %9,6.
    """

    def test_dso_olculduyse_ona_capalanir(self):
        a = _analiz([AcikVadeParcasi("customer", 5, 1_000_000, "M1", "M")],
                    dso=90.0, donem_gun=180)
        self.assertTrue(a.basabas_olculdu)
        self.assertFalse(a.basabas_alt_sinir)
        self.assertAlmostEqual(a.basabas_dayanak_gun, 90.0, places=1)
        self.assertAlmostEqual(a.basabas_kendi_vaden, 9.59, places=1)

    def test_vadeye_kalan_capa_olarak_kullanilmaz(self):
        """Kalan gün 5, DSO 90 → tavsiye 90'a göre olmalı (5'e göre %0,6 çıkardı)."""
        a = _analiz([AcikVadeParcasi("customer", 5, 1_000_000, "M1", "M")],
                    dso=90.0, donem_gun=180)
        self.assertAlmostEqual(a.alacak.agirlikli_gun, 5.0, places=1)
        self.assertGreater(a.basabas_kendi_vaden, 5.0,
                           "başabaş hâlâ «vadeye kalan»a çapalanmış")

    def test_pencere_kisaysa_tek_yonlu_sinir(self):
        """Kural 3: DSO pencereden uzunsa ölçülemez ama «en az» denebilir."""
        a = _analiz([AcikVadeParcasi("customer", 5, 1_000_000, "M1", "M")],
                    dso=211.0, donem_gun=180)
        self.assertFalse(a.basabas_olculdu)
        self.assertTrue(a.basabas_alt_sinir)
        self.assertAlmostEqual(a.basabas_dayanak_gun, 180.0, places=1)

    def test_satis_yoksa_capa_yok(self):
        a = _analiz([AcikVadeParcasi("customer", 5, 1_000_000, "M1", "M")],
                    dso=None, donem_gun=180)
        self.assertFalse(a.basabas_olculdu)
        self.assertFalse(a.basabas_alt_sinir)

    def test_makas_ozellikleri_kaldirildi(self):
        """Alacak & Borç'taki dso/dpo ile çelişen ikinci bir makas bir daha eklenmesin."""
        a = _analiz([AcikVadeParcasi("customer", 5, 1_000_000, "M1", "M")])
        for ad in ("makas_gun", "makas_var", "makas_lehte", "makas_maliyeti",
                   "makas_finanse_edilen", "tedarikci_kredisi_yok"):
            self.assertFalse(hasattr(a, ad), f"{ad} geri gelmiş — kural 5 ihlali")


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
        self.assertIn("BAŞABAŞ VADE FARKI;90 gün (%)", csv)
        self.assertIn("BAŞABAŞ VADE FARKI;90 gün (%)", csv)
        self.assertIn("EN ÇOK ERİTEN MÜŞTERİ;MUSTERI A", csv)
        self.assertIn("EN ÇOK KAZANDIRAN SATICI;SATICI B", csv)

    def test_dso_olculmediyse_csv_sebebini_yazar(self):
        a = _analiz([AcikVadeParcasi("customer", 90, 1_000_000, "M1", "M"),
                     AcikVadeParcasi("supplier", 30, 600_000, "S1", "S")])
        self.assertIn("BAŞABAŞ VADE FARKI;Tahsil süresi ölçülemedi", reel_deger_csv(a))

    def test_gecikmis_alacak_csvde_alt_sinir_sebebi(self):
        a = _analiz([AcikVadeParcasi("customer", 0, 500_000, "M1", "M")],
                    gecikmis=500_000.0)
        self.assertIn("Vade maliyeti alt sınır sebebi", reel_deger_csv(a))


if __name__ == "__main__":
    unittest.main()
