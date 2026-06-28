"""Tahsilat & Alacak motoru testleri — FIFO yaşlandırma, vade (cha_vade + plan), performans."""

import unittest

from tahsilat_alacak import (
    AGING_KOVALAR,
    VADE_KOVALAR,
    build_tahsilat_alacak,
    tahsilat_alacak_csv,
    _gun_vade_kovasi,
    _gun_yaslandirma_kovasi,
)


def _row(kod, tip, evrak, tutar, *, cha_vade=None, unvan="", donem=None):
    return {
        "kod": kod, "unvan": unvan or kod, "tip": tip,
        "evrak_tarihi": evrak, "cha_vade": cha_vade,
        "tutar": tutar, "tutar_donem": tutar if donem is None else donem,
    }


def _veri():
    return [
        # Müşteri 120 — iki satış (cha_vade dolu), kısmi tahsilat → FIFO eski borçtan düşer
        _row("120.01", 0, "2025-09-15", 100000, cha_vade="2025-10-01", unvan="A Ltd"),
        _row("120.01", 0, "2025-12-01", 50000, cha_vade="2025-12-15", unvan="A Ltd"),
        _row("120.01", 1, "2025-06-01", 60000, unvan="A Ltd"),
        # Satıcı 320 — bir alış, kısmi ödeme → kalan borç ileri vadeli (vadesi gelmemiş)
        _row("320.01", 1, "2025-12-20", 80000, cha_vade="2026-02-01", unvan="B AŞ"),
        _row("320.01", 0, "2025-07-01", 30000, unvan="B AŞ"),
        # Müşteri 120 — fazla tahsilat → avans (net 0, yaşlandırmaya girmez)
        _row("120.02", 0, "2025-11-01", 20000, cha_vade="2025-11-01", unvan="C San"),
        _row("120.02", 1, "2025-11-05", 30000, unvan="C San"),
    ]


class TestTahsilatAlacak(unittest.TestCase):
    def setUp(self):
        self.ta = build_tahsilat_alacak(_veri(), bas="2025-01-01", bit="2025-12-31")

    def test_toplamlar(self):
        self.assertAlmostEqual(self.ta.alacak_toplam, 90000, places=2)
        self.assertAlmostEqual(self.ta.borc_toplam, 50000, places=2)
        self.assertAlmostEqual(self.ta.net_pozisyon, 40000, places=2)
        self.assertAlmostEqual(self.ta.musteri_avans, 10000, places=2)
        self.assertEqual(self.ta.cari_sayisi, 2)  # 120.01 ve 320.01; 120.02 net 0
        self.assertEqual(self.ta.vade_kaynagi, "vade")  # cha_vade dolu satırlar var

    def test_fifo_yaslandirma(self):
        # 100000 satışın 60000'i kapandı → 40000 açık, vade 2025-10-01 (91 gün = 90+)
        self.assertAlmostEqual(self.ta.alacak_aging[AGING_KOVALAR[4]], 40000, places=2)
        # 50000 satış açık, vade 2025-12-15 (16 gün = 1–30)
        self.assertAlmostEqual(self.ta.alacak_aging[AGING_KOVALAR[1]], 50000, places=2)
        self.assertAlmostEqual(self.ta.alacak_gecikmis, 90000, places=2)

    def test_borc_vadesi_gelmemis(self):
        # Satıcı borcu vadesi 2026-02-01 → asof'tan sonra: vadesi gelmemiş, gecikmiş değil
        self.assertAlmostEqual(self.ta.borc_aging[AGING_KOVALAR[0]], 50000, places=2)
        self.assertAlmostEqual(self.ta.borc_gecikmis, 0, places=2)

    def test_vade_takvimi(self):
        nv = self.ta.net_vade()
        self.assertAlmostEqual(nv[VADE_KOVALAR[0]], 90000, places=2)        # gecikmiş alacak girecek
        self.assertAlmostEqual(self.ta.borc_vade[VADE_KOVALAR[3]], 50000, places=2)  # 32g → gelecek ay

    def test_performans(self):
        self.assertAlmostEqual(self.ta.donem_satis, 170000, places=2)
        self.assertAlmostEqual(self.ta.donem_tahsilat, 90000, places=2)
        self.assertAlmostEqual(self.ta.donem_alis, 80000, places=2)
        self.assertAlmostEqual(self.ta.donem_odeme, 30000, places=2)
        self.assertAlmostEqual(self.ta.tahsilat_orani, 90000 / 170000 * 100, places=1)
        self.assertIsNotNone(self.ta.dso)
        self.assertIsNotNone(self.ta.dpo)

    def test_top_listeler(self):
        self.assertEqual(self.ta.top_alacak[0].kod, "120.01")
        self.assertEqual(self.ta.top_borc[0].kod, "320.01")
        self.assertAlmostEqual(self.ta.top_alacak[0].gecikmis, 90000, places=2)

    def test_vade_plan_ile_hesaplanir(self):
        # cha_vade yok; vade = evrak tarihi + plan günü (30) → 2025-12-31 = asof → vadesi gelmemiş
        rows = [_row("120.07", 0, "2025-12-01", 10000)]
        ta = build_tahsilat_alacak(rows, vade_gun_map={"120.07": 30},
                                   bas="2025-01-01", bit="2025-12-31")
        self.assertAlmostEqual(ta.alacak_aging[AGING_KOVALAR[0]], 10000, places=2)
        self.assertAlmostEqual(ta.alacak_gecikmis, 0, places=2)
        self.assertEqual(ta.vade_kaynagi, "plan")

    def test_plan_yoksa_evrak_tarihi(self):
        # cha_vade yok, plan yok → vade = evrak tarihi → gecikmiş
        rows = [_row("120.08", 0, "2025-01-15", 5000)]
        ta = build_tahsilat_alacak(rows, bas="2025-01-01", bit="2025-12-31")
        self.assertAlmostEqual(ta.alacak_gecikmis, 5000, places=2)
        self.assertEqual(ta.vade_kaynagi, "tarih")

    def test_sinif_kod_onekinden(self):
        # 320 → satıcı; 120/320 dışı kod elenir
        rows = [
            _row("320.99", 1, "2026-03-01", 5000, cha_vade="2026-03-01"),
            _row("320.99", 0, "2025-01-01", 1000),
            _row("999.00", 0, "2025-01-01", 7000),  # cari değil → atlanır
        ]
        ta = build_tahsilat_alacak(rows, bas="2025-01-01", bit="2025-12-31")
        self.assertAlmostEqual(ta.borc_toplam, 4000, places=2)
        self.assertAlmostEqual(ta.alacak_toplam, 0, places=2)

    def test_csv(self):
        csv = tahsilat_alacak_csv(self.ta)
        self.assertIn("ALACAK YAŞLANDIRMA", csv)
        self.assertIn("VADE TAKVİMİ", csv)
        self.assertIn("Tahsilat Oranı", csv)

    def test_kova_sinirlari(self):
        self.assertEqual(_gun_yaslandirma_kovasi(0), AGING_KOVALAR[0])
        self.assertEqual(_gun_yaslandirma_kovasi(1), AGING_KOVALAR[1])
        self.assertEqual(_gun_yaslandirma_kovasi(30), AGING_KOVALAR[1])
        self.assertEqual(_gun_yaslandirma_kovasi(31), AGING_KOVALAR[2])
        self.assertEqual(_gun_yaslandirma_kovasi(91), AGING_KOVALAR[4])
        self.assertEqual(_gun_vade_kovasi(-1), VADE_KOVALAR[0])
        self.assertEqual(_gun_vade_kovasi(7), VADE_KOVALAR[1])
        self.assertEqual(_gun_vade_kovasi(45), VADE_KOVALAR[3])
        self.assertEqual(_gun_vade_kovasi(120), VADE_KOVALAR[4])

    def test_bos_veri(self):
        ta = build_tahsilat_alacak([], bas="2025-01-01", bit="2025-12-31")
        self.assertEqual(ta.cari_sayisi, 0)
        self.assertIsNone(ta.dso)
        self.assertAlmostEqual(ta.net_pozisyon, 0, places=2)


class TestCariVade(unittest.TestCase):
    def test_hesapla_vade_gun(self):
        from cari_vade import hesapla_vade_gun, gun_from_plan_adi
        self.assertEqual(hesapla_vade_gun(-60, None, None), 60)   # negatif plan = gün
        self.assertEqual(hesapla_vade_gun(0, None, None), 0)      # peşin
        self.assertEqual(hesapla_vade_gun(2, None, 45), 45)       # odp_ortgun öncelikli
        self.assertEqual(hesapla_vade_gun(2, "30 GÜN", 0), 30)    # plan adından
        self.assertEqual(hesapla_vade_gun(3, None, None), 60)     # bilinen plan no tablosu
        self.assertEqual(gun_from_plan_adi("PEŞİN"), 0)
        self.assertEqual(gun_from_plan_adi("90 gün vade"), 90)
        self.assertIsNone(gun_from_plan_adi("bilinmeyen"))


if __name__ == "__main__":
    unittest.main()
