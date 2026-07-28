"""
Kurulum tanıma — program başka bir Mikro kurulumunda da doğru rakam göstermeli.

Bu, ürünün başkalarına satılabilmesinin ön şartı. Hesaplama kuralları şimdiye kadar
VARSAYIMDI ve varsayılanları tek bir firmanın iş akışına göreydi; aynı veride
«İrsaliye + Fatura» 20.481.407 TL derken «Yalnız Fatura» 1.095.172 TL diyor. On dokuz
kat. Yanlış varsayımla açılan bir demo geri kazanılmaz.
"""

from __future__ import annotations

import unittest

from domain.kurulum import KESIN, ZAYIF, kurulumu_tespit_et

# Canlı kurulum: satışta damgalama modeli, alışta girişlerin tamamı depo transferi.
_CANLI_FATURALASMA = [
    {"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 1, "adet": 17430,
     "tutar": 18_551_641.73},
    {"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 0, "adet": 484, "tutar": 834_593.09},
    {"sth_tip": 1, "sth_evraktip": 4, "faturalandi": 1, "adet": 262,
     "tutar": 1_095_172.64},
    {"sth_tip": 0, "sth_evraktip": 12, "faturalandi": 0, "adet": 6592,
     "tutar": 22_594_651.34},
    {"sth_tip": 0, "sth_evraktip": 3, "faturalandi": 1, "adet": 2492,
     "tutar": 14_665_701.10},
]
_CANLI_DEPO = [{"transfer": 1, "tutar": 22_594_651.34, "adet": 6592}]


class TestCanliKurulum(unittest.TestCase):
    """Elle vardığımız sonucun aynısına ölçerek varmalı."""

    def setUp(self) -> None:
        self.k = kurulumu_tespit_et(_CANLI_FATURALASMA, _CANLI_DEPO)

    def test_satis_irsaliye_ve_fatura(self) -> None:
        self.assertEqual(self.k.deger("satis_bazi"), "sevk")

    def test_alis_yalniz_fatura(self) -> None:
        self.assertEqual(self.k.deger("alis_bazi"), "fatura")

    def test_ikisi_de_kesin(self) -> None:
        self.assertEqual(self.k.kesin_sayisi, 2)
        for t in self.k.tespitler:
            self.assertEqual(t.guven, KESIN, t.alan)

    def test_gerekce_rakam_tasir(self) -> None:
        """Kullanıcı ayarı neden değiştirdiğimizi görmeli; «öyle uygun» yetmez."""
        satis = next(t for t in self.k.tespitler if t.alan == "satis_bazi")
        self.assertIn("17.430", satis.gerekce)
        self.assertIn("262", satis.gerekce)


class TestKopyalamaModeli(unittest.TestCase):
    """
    Faturalaşınca İKİNCİ satır doğuran kurulum — toplamak satışı iki kat şişirir.

    Bizim kurulumumuzda böyle değil; başka bir firmada olabilir ve program bunu
    kendiliğinden görmeli.
    """

    def test_yalniz_fatura_onerilir(self) -> None:
        rows = [
            {"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 1, "adet": 5000,
             "tutar": 10_000_000.0},
            {"sth_tip": 1, "sth_evraktip": 4, "faturalandi": 1, "adet": 4900,
             "tutar": 9_800_000.0},
        ]
        k = kurulumu_tespit_et(rows, [])
        self.assertEqual(k.deger("satis_bazi"), "fatura")
        satis = next(t for t in k.tespitler if t.alan == "satis_bazi")
        self.assertIn("iki kat", satis.gerekce)


class TestGercekAlisIrsaliyesi(unittest.TestCase):
    """Mal irsaliyeyle giren kurulumda alışta irsaliye sayılmalı."""

    def test_irsaliye_onerilir(self) -> None:
        rows = [
            {"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 1, "adet": 900,
             "tutar": 5_000_000.0},
            {"sth_tip": 1, "sth_evraktip": 4, "faturalandi": 1, "adet": 10,
             "tutar": 50_000.0},
            {"sth_tip": 0, "sth_evraktip": 12, "faturalandi": 1, "adet": 800,
             "tutar": 4_000_000.0},
            {"sth_tip": 0, "sth_evraktip": 3, "faturalandi": 1, "adet": 20,
             "tutar": 100_000.0},
        ]
        # Girişlerin tamamı DIŞARIDAN (çıkış deposu yok) → transfer değil, gerçek alış.
        depo = [{"transfer": 0, "tutar": 4_000_000.0, "adet": 800}]
        k = kurulumu_tespit_et(rows, depo)
        self.assertEqual(k.deger("alis_bazi"), "irsaliye")


class TestEminOlamayinca(unittest.TestCase):
    """
    Ölçüm zayıfsa AYAR DEĞİŞMEZ.

    Yanlış bir otomatik ayar, elle seçilmiş bir ayardan daha zararlıdır: kullanıcı onu
    kendi seçmediği için sorgulamaz.
    """

    def test_veri_yoksa_karar_yok(self) -> None:
        k = kurulumu_tespit_et([], [])
        self.assertEqual(k.kesin_sayisi, 0)
        self.assertIsNone(k.deger("satis_bazi"))
        for t in k.tespitler:
            self.assertEqual(t.guven, ZAYIF)

    def test_az_hareket_karar_verdirmez(self) -> None:
        rows = [{"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 1, "adet": 3,
                 "tutar": 900.0}]
        k = kurulumu_tespit_et(rows, [])
        self.assertIsNone(k.deger("satis_bazi"))

    def test_hic_cagrilmadiysa_bos_doner(self) -> None:
        k = kurulumu_tespit_et(None, None)
        self.assertEqual(k.tespitler, [])
        self.assertIn("okunamadı", k.ozet())

    def test_depo_kirilimi_yoksa_alis_degismez(self) -> None:
        """Alış irsaliyesi var ama gerçek mal mı transfer mi bilinmiyorsa karışma."""
        rows = [
            {"sth_tip": 1, "sth_evraktip": 1, "faturalandi": 1, "adet": 900,
             "tutar": 5_000_000.0},
            {"sth_tip": 0, "sth_evraktip": 12, "faturalandi": 0, "adet": 800,
             "tutar": 4_000_000.0},
            {"sth_tip": 0, "sth_evraktip": 3, "faturalandi": 1, "adet": 700,
             "tutar": 3_500_000.0},
        ]
        k = kurulumu_tespit_et(rows, [])
        self.assertIsNone(k.deger("alis_bazi"))


if __name__ == "__main__":
    unittest.main()
