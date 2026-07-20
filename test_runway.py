"""domain.runway nakit runway motoru için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.nakit_akis import AyNakit, NakitAkis
from domain.runway import (
    build_runway,
    build_runway_takvim,
    runway_nakit_akistan,
    runway_takvim_kur,
)
from domain.tahsilat_alacak import VADE_KOVALAR


class TestRunway(unittest.TestCase):
    def test_eriyen_nakit_tukenme(self):
        # 100k nakit, ayda -20k → 5 ay sonra 0, 6. ay eksiye düşer.
        r = build_runway(baslangic_nakit=100000.0, aylik_net_ort=-20000.0,
                         baslangic_ay="2026-06", ufuk_ay=12)
        self.assertTrue(r.eriyor)
        self.assertFalse(r.surdurulebilir)
        self.assertEqual(r.tukenme_ay, "2026-12")   # 6 ay sonra
        self.assertAlmostEqual(r.tukenme_gun, round(5 * 30.44), delta=1)

    def test_surdurulebilir_nakit(self):
        r = build_runway(baslangic_nakit=50000.0, aylik_net_ort=10000.0,
                         baslangic_ay="2026-06", ufuk_ay=12)
        self.assertFalse(r.eriyor)
        self.assertTrue(r.surdurulebilir)
        self.assertIsNone(r.tukenme_ay)
        self.assertAlmostEqual(r.en_dusuk_nakit, 50000.0, places=2)

    def test_zaten_negatif_nakit(self):
        r = build_runway(baslangic_nakit=-5000.0, aylik_net_ort=-1000.0,
                         baslangic_ay="2026-06", ufuk_ay=6)
        self.assertEqual(r.tukenme_ay, "2026-07")  # ilk ay
        self.assertEqual(r.tukenme_gun, 0)

    def test_ufuk_disinda_tukenme_yok(self):
        # Yavaş erime, kısa ufuk → ufuk içinde tükenmez ama trend negatif
        r = build_runway(baslangic_nakit=100000.0, aylik_net_ort=-1000.0,
                         baslangic_ay="2026-06", ufuk_ay=3)
        self.assertTrue(r.eriyor)
        self.assertTrue(r.surdurulebilir)   # ufuk içinde eksiye düşmedi
        self.assertIsNone(r.tukenme_ay)

    def test_nakit_akistan_ortalama(self):
        na = NakitAkis(
            bit="2026-06-30", kapanis_nakit=90000.0,
            aylik=[
                AyNakit("2026-04", giris=10000.0, cikis=40000.0),  # net -30k
                AyNakit("2026-05", giris=20000.0, cikis=30000.0),  # net -10k
            ],
        )
        r = runway_nakit_akistan(na)
        self.assertAlmostEqual(r.aylik_net_ort, -20000.0, places=2)  # (-30k-10k)/2
        self.assertEqual(r.baslangic_nakit, 90000.0)
        self.assertTrue(r.eriyor)


class TestRunwayTakvim(unittest.TestCase):
    def test_takvim_tukenme(self):
        # 100k nakit; 1. ay 20k girer, aylık düzenli gider 60k → 1. ay -40k akış
        r = build_runway_takvim(
            baslangic_nakit=100000.0, baslangic_ay="2026-06",
            alacak_vade={VADE_KOVALAR[1]: 20000.0},   # Bu hafta → 1. ay
            borc_vade={VADE_KOVALAR[3]: 10000.0},      # Gelecek ay → 2. ay
            aylik_gider=60000.0, ufuk_ay=6,
        )
        # Ay1: +20k -60k = -40k → nakit 60k. Ay2: -10k -60k = -70k → nakit -10k → tükenir.
        self.assertEqual(r.aylar[0].nakit, 60000.0)
        self.assertEqual(r.tukenme_ay, "2026-08")
        self.assertFalse(r.surdurulebilir)

    def test_takvim_saglikli(self):
        r = build_runway_takvim(
            baslangic_nakit=200000.0, baslangic_ay="2026-06",
            alacak_vade={VADE_KOVALAR[1]: 100000.0}, borc_vade={},
            aylik_gider=10000.0, ufuk_ay=4,
        )
        self.assertIsNone(r.tukenme_ay)
        self.assertTrue(r.surdurulebilir)

    def test_gider_eksik_bayragi(self):
        eksik = build_runway_takvim(
            baslangic_nakit=500000.0, baslangic_ay="2026-06",
            alacak_vade={VADE_KOVALAR[1]: 100000.0}, borc_vade={},
            aylik_gider=0.0, aylik_kredi=0.0, ufuk_ay=3,
        )
        self.assertTrue(eksik.gider_eksik)
        tam = build_runway_takvim(
            baslangic_nakit=500000.0, baslangic_ay="2026-06",
            alacak_vade={}, borc_vade={}, aylik_gider=50000.0, ufuk_ay=3,
        )
        self.assertFalse(tam.gider_eksik)

    def test_gl_nakit_override(self):
        # Şişik cari kapanış (24.7M) yerine GL nakit (530k) başlangıç kullanılmalı.
        na = NakitAkis(bit="2026-06-30", kapanis_nakit=24_700_000.0,
                       aylik=[AyNakit("2026-05", giris=0.0, cikis=0.0)])

        class _TA:
            alacak_vade: dict = {}
            borc_vade: dict = {}

        r = runway_takvim_kur(na=na, ta=_TA(), baslangic_nakit=530000.0, ufuk_ay=3)
        self.assertEqual(r.baslangic_nakit, 530000.0)  # cari 24.7M DEĞİL

    def test_gider_kredi_override(self):
        # Gider/kredi override verilince nakit-kategorisi yerine onlar kullanılmalı.
        na = NakitAkis(bit="2026-06-30", kapanis_nakit=100000.0,
                       aylik=[AyNakit("2026-05", giris=0.0, cikis=0.0)])

        class _TA:
            alacak_vade: dict = {}
            borc_vade: dict = {}

        r = runway_takvim_kur(na=na, ta=_TA(), aylik_gider=30000.0, aylik_kredi=10000.0,
                              ufuk_ay=2)
        self.assertFalse(r.gider_eksik)           # override ile gider var
        self.assertAlmostEqual(r.aylar[0].cikan, 40000.0, places=2)  # 30k + 10k

    def test_nakit_gl_ozetten(self):
        from domain.nakit_akis import nakit_gl_ozetten
        rows = [
            {"ana": "100", "bakiye": 175941.0},
            {"ana": "102", "bakiye": 114629.0},
            {"ana": "108", "bakiye": 238951.0},
            {"ana": "120", "bakiye": 6_400_000.0},  # alacak — nakit değil, sayılmaz
        ]
        self.assertAlmostEqual(nakit_gl_ozetten(rows), 529521.0, places=0)

    def test_takvim_kur_adaptor(self):
        na = NakitAkis(
            bit="2026-06-30", kapanis_nakit=150000.0,
            aylik=[AyNakit("2026-05", giris=0.0, cikis=0.0)],
            cikis_kategori={"Personel / Maaş": 30000.0, "Genel giderler": 10000.0},
            kredi_odeme=20000.0,
        )

        class _TA:
            alacak_vade = {VADE_KOVALAR[1]: 50000.0}
            borc_vade = {VADE_KOVALAR[1]: 5000.0}

        r = runway_takvim_kur(na=na, ta=_TA(), ufuk_ay=3)
        # düzenli gider = (30k+10k)/1 = 40k ; kredi = 20k/1 = 20k
        self.assertAlmostEqual(r.aylik_gider, 40000.0, places=2)
        self.assertAlmostEqual(r.aylik_kredi, 20000.0, places=2)
        # Ay1: +50k -(5k+40k+20k)= -15k → nakit 135k
        self.assertAlmostEqual(r.aylar[0].nakit, 135000.0, places=2)


if __name__ == "__main__":
    unittest.main()
