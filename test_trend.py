"""Trend & Oranlar — domain birim testleri."""

from __future__ import annotations

import math
import unittest

from domain.ai_yorum import YilKapanis, yillar_arasi_csv
from domain.gercek_durum import AyTrend
from domain.mizan_bilanco import build_bilanco
from domain.trend import build_finansal_oranlar, build_trend, trend_csv
from infra.mukayese_fetch import yil_donemleri


class TestTrend(unittest.TestCase):
    def test_cok_yilli_donem_yillara_bolunur(self) -> None:
        self.assertEqual(
            yil_donemleri("2025-07-28", "2026-07-28"),
            [
                (2025, "2025-07-28", "2025-12-31"),
                (2026, "2026-01-01", "2026-07-28"),
            ],
        )

    def test_ters_tarih_hata_verir(self) -> None:
        with self.assertRaises(ValueError):
            yil_donemleri("2026-01-01", "2025-12-31")

    def test_kismi_yil_csv_notu_ayni_ytd_kiyasini_aciklar(self) -> None:
        csv = yillar_arasi_csv([
            YilKapanis(yil=2025, bit="2025-07-28", tam=False, net_satis=100),
            YilKapanis(yil=2026, bit="2026-07-28", tam=False, net_satis=120),
        ])
        self.assertIn("2025 (01.01–28.07)", csv)
        self.assertIn("aynı tarih penceresiyle hazırlanmış diğer YTD", csv)

    def test_oranlar_bilanco(self) -> None:
        b = build_bilanco([
            {"hesap_kodu": "100", "borc": 5000.0, "alacak": 0.0},
            {"hesap_kodu": "120", "borc": 15000.0, "alacak": 0.0},
            {"hesap_kodu": "150", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 20000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 10000.0},
        ], asof="2026-06-30")
        oranlar, ozet = build_finansal_oranlar(b)
        self.assertGreater(ozet["donen"], 0)
        self.assertGreater(ozet["kvyk"], 0)
        cari = next(o for o in oranlar if o.kod == "cari")
        self.assertIsNotNone(cari.deger)
        self.assertAlmostEqual(cari.deger or 0, ozet["donen"] / ozet["kvyk"], places=4)

    def test_build_trend_ve_csv(self) -> None:
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 8000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 4000.0},
        ], asof="2026-06-30")
        aylik = [
            AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000),
            AyTrend(ay="2026-02", satis=12000, alis=7000, nakit_giren=9000, nakit_cikan=6000),
        ]
        tr = build_trend(aylik=aylik, bilanco=b, bas="2026-01-01", bit="2026-06-30")
        self.assertEqual(tr.ay_sayisi, 2)
        self.assertEqual(tr.toplam_satis, 22000)
        self.assertTrue(tr.oranlar)
        csv = trend_csv(tr)
        self.assertIn("ORAN;", csv)
        self.assertIn("AYLIK;2026-01 Satış;", csv)
        self.assertIn("KAYNAK;Aylık Satış / Alış / Brüt", csv)
        self.assertIn("İlk ve son ay kısmi olabilir", csv)

    def test_gecmis_penceresi_kpi_toplamlarini_bozmaz(self) -> None:
        """Grafik son 12 ayı gösterse de KPI toplamları SEÇİLİ dönemden gelmeli."""
        donem = [AyTrend(ay="2026-06", satis=10000, alis=6000),
                 AyTrend(ay="2026-07", satis=12000, alis=7000)]
        gecmis = [AyTrend(ay=f"2026-{m:02d}", satis=5000, alis=3000) for m in range(1, 6)] + donem
        tr = build_trend(aylik=donem, aylik_gecmis=gecmis, bas="2026-06-01", bit="2026-07-31")
        self.assertEqual(tr.toplam_satis, 22000)   # yalnız seçili dönem
        self.assertEqual(tr.ay_sayisi, 2)
        self.assertEqual(len(tr.aylik_gecmis), 7)  # grafik daha uzun pencereyi görür

    def test_gecmis_verilmezse_grafik_donemi_gosterir(self) -> None:
        donem = [AyTrend(ay="2026-07", satis=12000, alis=7000)]
        tr = build_trend(aylik=donem, bas="2026-07-01", bit="2026-07-31")
        self.assertEqual(tr.aylik_gecmis, [])


class TestTrendGrafikYardimcilari(unittest.TestCase):
    def test_ay_etiketi_turkce(self) -> None:
        from ui.trend_view import _ay_etiket
        self.assertEqual(_ay_etiket("2026-01"), "Oca 26")
        self.assertEqual(_ay_etiket("2025-12"), "Ara 25")
        self.assertEqual(_ay_etiket("bozuk"), "bozuk")

    def test_kisa_tutar(self) -> None:
        from ui.trend_view import _kisa_tutar
        self.assertEqual(_kisa_tutar(0), "0")
        self.assertEqual(_kisa_tutar(356_949), "357B")
        self.assertEqual(_kisa_tutar(5_923_722), "5,9M")
        self.assertEqual(_kisa_tutar(-2_000_000), "-2,0M")

    def test_guzel_adim_yuvarlak(self) -> None:
        from ui.trend_view import _guzel_adim
        for aralik in (1_000.0, 37_512.0, 4_180_000.0, 23_000_000.0):
            adim = _guzel_adim(aralik)
            self.assertGreater(adim, 0)
            # 1/2/2,5/5/10 × 10ⁿ formunda olmalı → mantis kısa listede
            mantis = adim / (10 ** math.floor(math.log10(adim)))
            self.assertIn(round(mantis, 3), (1.0, 2.0, 2.5, 5.0, 10.0))


class TestNegatifOzkaynak(unittest.TestCase):
    """
    Özkaynak eksiyken Borç/Özkaynak hesaplanmamalı.

    Canlı PDF'te FİNANSAL ORANLAR paneli «-21,78» yazarken aynı raporun mukayese
    tablosu «—» diyordu: aynı oran, aynı veri, iki farklı cevap. Eksi paydada sonuç
    da eksi çıkar ve «borcum az» gibi okunur; oysa özkaynak tükenmiştir.
    """

    @staticmethod
    def _bilanco(ozkaynak_alacak: float):
        return build_bilanco([
            {"hesap_kodu": "102", "borc": 50_000.0, "alacak": 0},
            {"hesap_kodu": "153", "borc": 150_000.0, "alacak": 0},
            {"hesap_kodu": "320", "borc": 0, "alacak": 180_000.0},
            {"hesap_kodu": "500", "borc": 0, "alacak": ozkaynak_alacak},
        ], asof="2025-12-31")

    @staticmethod
    def _oran(b, kod: str):
        return next(o for o in build_finansal_oranlar(b)[0] if o.kod == kod)

    def test_eksi_ozkaynakta_borc_oz_hesaplanmaz(self) -> None:
        b = self._bilanco(-40_000.0)          # alacak eksi → özkaynak eksi
        self.assertLess(build_finansal_oranlar(b)[1]["ozkaynak"], 0)
        self.assertIsNone(self._oran(b, "borc_oz").deger)
        self.assertEqual(self._oran(b, "borc_oz").metin(), "—")

    def test_pozitif_ozkaynakta_hesaplanir(self) -> None:
        b = self._bilanco(20_000.0)
        self.assertIsNotNone(self._oran(b, "borc_oz").deger)

    def test_ozkaynak_orani_eksi_kalabilir(self) -> None:
        """Bu oran eksiyken de bilgi taşır: borçlar varlıkları aşmış demektir."""
        b = self._bilanco(-40_000.0)
        self.assertIsNotNone(self._oran(b, "oz_oran").deger)


if __name__ == "__main__":
    unittest.main()
