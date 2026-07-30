"""
KDV nakit köprüsü — KDV bir gider değil, finansman yüküdür.

Kullanıcının sorusu birebir şuydu: «100 TL'lik mal satıyoruz, %20 KDV'si 20 TL'yi aynı
ay devlete ödüyoruz. Ama biz o 100 TL'yi müşteriden ortalama 90 günde tahsil ediyorsak
bu nakit akışta önemsiz bir şey mi?» Değil — ve bu testler o farkın sessizce kaybolmasını
engeller.
"""

from __future__ import annotations

import unittest

from domain.kdv import build_kdv_koprusu, kdv_csv

# Bir dönemin KDV hareketleri: 391 satıştan doğar (ALACAK), 191 alıştan (BORÇ).
# Ay sonu mahsup fişi (391 borç / 191 alacak / 360) bu iki tarafa dokunmaz.
_ROWS = [
    {"ay": "2026-01", "hesap": "391", "borc": 0.0, "alacak": 200_000.0},
    {"ay": "2026-01", "hesap": "191", "borc": 120_000.0, "alacak": 0.0},
    {"ay": "2026-02", "hesap": "391", "borc": 0.0, "alacak": 300_000.0},
    {"ay": "2026-02", "hesap": "191", "borc": 180_000.0, "alacak": 0.0},
    # Ay sonu mahsup: 391 borçlanır, 191 alacaklanır — SAYILMAMALI.
    {"ay": "2026-02", "hesap": "391", "borc": 500_000.0, "alacak": 0.0},
    {"ay": "2026-02", "hesap": "191", "borc": 0.0, "alacak": 300_000.0},
]


def _kdv(**kw):
    args = {"net_satis": 2_500_000.0, "alacak": 1_200_000.0,
            "bas": "2026-01-01", "bit": "2026-02-28"}
    args.update(kw)
    return build_kdv_koprusu(_ROWS, **args)


class TestDogusTarafi(unittest.TestCase):
    """Mahsup fişi mükerrer saydırmamalı — yoksa KDV yükü iki katı görünür."""

    def test_hesaplanan_yalniz_alacak_tarafindan(self) -> None:
        self.assertAlmostEqual(_kdv().hesaplanan, 500_000.0)

    def test_indirilecek_yalniz_borc_tarafindan(self) -> None:
        self.assertAlmostEqual(_kdv().indirilecek, 300_000.0)

    def test_net_kdv_devlete_kalan(self) -> None:
        self.assertAlmostEqual(_kdv().net_kdv, 200_000.0)

    def test_aylik_kirilim(self) -> None:
        aylik = _kdv().aylik
        self.assertEqual([a.ay for a in aylik], ["2026-01", "2026-02"])
        self.assertAlmostEqual(aylik[0].net, 80_000.0)
        self.assertAlmostEqual(aylik[1].net, 120_000.0)


class TestOranOlculur(unittest.TestCase):
    """
    ORAN VARSAYILMAZ (CLAUDE.md kural 6).

    «KDV %20'dir» demek başka bir kurulumda sessizce yanlış rakam demektir: ürün karması
    %1/%10/%20 karışık olabilir, ihracat satışında KDV hiç doğmaz.
    """

    def test_efektif_oran_donemin_kendi_rakami(self) -> None:
        # 500.000 / 2.500.000 = %20
        self.assertAlmostEqual(_kdv().oran, 20.0)

    def test_ihracat_agirlikli_kurulumda_oran_dusuk_cikar(self) -> None:
        k = _kdv(net_satis=10_000_000.0)
        self.assertAlmostEqual(k.oran, 5.0)

    def test_satis_yoksa_oran_uydurulmaz(self) -> None:
        k = _kdv(net_satis=0.0)
        self.assertIsNone(k.oran)
        self.assertIn("net satış", k.sebep)


class TestAlacaktakiKdv(unittest.TestCase):
    """Asıl mesele: bu para devlete ödendi ama müşteriden henüz alınmadı."""

    def test_alacagin_icindeki_kdv(self) -> None:
        # Alacak KDV DÂHİL: 1.200.000 × 20/120 = 200.000
        self.assertAlmostEqual(_kdv().alacaktaki_kdv, 200_000.0, places=2)

    def test_alacak_yoksa_hesaplanmaz(self) -> None:
        self.assertIsNone(_kdv(alacak=0.0).alacaktaki_kdv)

    def test_tahsil_suresi_brut_satistan(self) -> None:
        """Alacak KDV dâhil; NET satışa bölmek süreyi şişirirdi."""
        k = _kdv()
        # brüt satış 3.000.000, dönem 59 gün → günlük 50.847; 1.200.000 / 50.847 ≈ 23,6
        self.assertAlmostEqual(k.tahsil_gun, 1_200_000.0 / (3_000_000.0 / 59), places=1)

    def test_uzun_vade_daha_cok_kdv_finansmani_demek(self) -> None:
        """Aynı ciroda alacak iki katına çıkarsa finanse edilen KDV de iki katıdır."""
        az, cok = _kdv(alacak=1_200_000.0), _kdv(alacak=2_400_000.0)
        self.assertAlmostEqual(cok.alacaktaki_kdv, az.alacaktaki_kdv * 2, places=2)
        self.assertGreater(cok.tahsil_gun, az.tahsil_gun)


class TestOkunamayanKaynak(unittest.TestCase):
    """
    Okunamayan alan, sıfır çıkan alandan farklıdır (CLAUDE.md kural 2).

    Panel hiç çizilmez; çizilseydi «KDV yükünüz yok» gibi okunurdu.
    """

    def test_hic_cagrilmadiysa_var_degil(self) -> None:
        k = build_kdv_koprusu(None, bas="2026-01-01", bit="2026-02-28")
        self.assertFalse(k.var)
        self.assertIn("okunamadı", k.sebep)
        self.assertEqual(kdv_csv(k), "")

    def test_kdv_hesabi_hic_hareket_gormemisse_sebep_yazilir(self) -> None:
        k = build_kdv_koprusu([], net_satis=2_500_000.0, alacak=1_000_000.0,
                              bas="2026-01-01", bit="2026-02-28")
        self.assertTrue(k.var)
        self.assertIsNone(k.oran)
        self.assertIn("391", k.sebep)

    def test_bozuk_tarihte_cokmez(self) -> None:
        k = build_kdv_koprusu(_ROWS, net_satis=1.0, alacak=1.0, bas="", bit="")
        self.assertEqual(k.gun, 0)
        self.assertIsNone(k.tahsil_gun)


class TestCsv(unittest.TestCase):
    def test_csv_ana_kalemleri_tasir(self) -> None:
        csv = kdv_csv(_kdv())
        self.assertIn("KDV;Devlete kalan net KDV;200000,00", csv)
        self.assertIn("KDV;Tahsil edilmemiş alacaktaki KDV;200000,00", csv)
        self.assertIn("KDV AYLIK;2026-01 net;80000,00", csv)


if __name__ == "__main__":
    unittest.main()
