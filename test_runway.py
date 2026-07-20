"""domain.runway nakit runway motoru için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.nakit_akis import AyNakit, NakitAkis
from domain.runway import build_runway, runway_nakit_akistan


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


if __name__ == "__main__":
    unittest.main()
