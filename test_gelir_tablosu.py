"""domain.gelir_tablosu build_gelir_tablosu için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.gelir_tablosu import build_gelir_tablosu, gelir_dagilimi, gider_dagilimi


def _satir(kod: str, tutar: float) -> dict:
    """Gelir tablosu işaretiyle (gelir +, gider −) mizan satırı üretir."""
    return {"hesap_kodu": kod,
            "borc": 0.0 if tutar >= 0 else -tutar,
            "alacak": tutar if tutar >= 0 else 0.0}


class TestGelirTablosu(unittest.TestCase):
    def test_faaliyet_ve_finansman_gideri(self):
        # tutar = alacak − borç → gider hesapları negatif çıkar
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0, "alacak": 100000},
            {"hesap_kodu": "631", "borc": 15000, "alacak": 0},   # 63 pazarlama gideri
            {"hesap_kodu": "632", "borc": 5000, "alacak": 0},    # 63 genel yönetim
            {"hesap_kodu": "660", "borc": 4000, "alacak": 0},    # 66 finansman
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertAlmostEqual(gt.faaliyet_gideri, -20000.0, places=2)  # 63 toplam
        self.assertAlmostEqual(gt.finansman_gideri, -4000.0, places=2)  # 66 toplam

    def test_gider_yoksa_sifir(self):
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0, "alacak": 50000},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertEqual(gt.faaliyet_gideri, 0.0)
        self.assertEqual(gt.finansman_gideri, 0.0)


class TestDagilim(unittest.TestCase):
    """Pasta dilimleri: para nereden geliyor / nereye gidiyor."""

    @staticmethod
    def _gt(*kalemler):
        return build_gelir_tablosu([_satir(k, v) for k, v in kalemler],
                                   bas="2025-01-01", bit="2025-12-31")

    def test_gelir_eksi_gider_net_kari_verir(self) -> None:
        """Dağılımlar şelaleyle mutabık olmalı — yoksa pasta yalan söyler."""
        gt = self._gt(("600", 100_000.0), ("601", 20_000.0), ("610", -5_000.0),
                      ("621", -70_000.0), ("632", -12_000.0), ("642", 3_000.0),
                      ("660", -2_000.0), ("691", -1_500.0))
        gelir = sum(d.tutar for d in gelir_dagilimi(gt))
        gider = sum(d.tutar for d in gider_dagilimi(gt))
        self.assertAlmostEqual(gelir - gider, gt.net_kar, places=2)

    def test_iade_gider_tarafinda(self) -> None:
        """61 satış indirimi bir sızıntıdır; eksi dilim çizilemeyeceği için gider olur."""
        gt = self._gt(("600", 100_000.0), ("610", -5_000.0), ("621", -70_000.0))
        self.assertIn("Satıştan İadeler", [d.etiket for d in gider_dagilimi(gt)])
        self.assertNotIn("Satıştan İadeler", [d.etiket for d in gelir_dagilimi(gt)])

    def test_paylar_yuze_tamamlanir(self) -> None:
        for dilimler in (gelir_dagilimi(self._gt(("600", 90.0), ("601", 10.0))),
                         gider_dagilimi(self._gt(("600", 100.0), ("621", 60.0 * -1),
                                                 ("632", -40.0)))):
            self.assertAlmostEqual(sum(d.pay for d in dilimler), 100.0, places=2)

    def test_kucuk_kalemler_digerde_toplanir(self) -> None:
        gt = self._gt(("600", 1_000_000.0), ("601", 2_000.0), ("602", 2_000.0),
                      ("642", 2_000.0))
        etiketler = [d.etiket for d in gelir_dagilimi(gt)]
        self.assertEqual(etiketler, ["Yurtiçi Satışlar", "Diğer (3 kalem)"])

    def test_tek_kucuk_kalem_diger_olmaz(self) -> None:
        """Tek kalemi 'Diğer' diye gizlemek adını saklamaktan başka işe yaramaz."""
        gt = self._gt(("600", 1_000_000.0), ("601", 2_000.0))
        self.assertEqual([d.etiket for d in gelir_dagilimi(gt)],
                         ["Yurtiçi Satışlar", "Yurtdışı Satışlar"])

    def test_kapanis_aynasi_dagilimda_yok(self) -> None:
        """690/692 şelalede yok; dağılımda olsa gider iki kat görünürdü."""
        gt = self._gt(("600", 100_000.0), ("621", -60_000.0), ("690", -40_000.0))
        self.assertEqual([d.etiket for d in gider_dagilimi(gt)],
                         ["Satılan Ticari Mallar Maliyeti"])

    def test_veri_yoksa_dilim_yok(self) -> None:
        gt = self._gt(("600", 100_000.0))
        self.assertEqual(gider_dagilimi(gt), [])


if __name__ == "__main__":
    unittest.main()
