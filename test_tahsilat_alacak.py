"""Tahsilat & Alacak motoru testleri — FIFO yaşlandırma, vade takvimi, performans."""

import unittest

from tahsilat_alacak import (
    AGING_KOVALAR,
    VADE_KOVALAR,
    build_tahsilat_alacak,
    tahsilat_alacak_csv,
    _gun_vade_kovasi,
    _gun_yaslandirma_kovasi,
)


def _row(kod, muh, tip, vade, tutar, *, unvan="", donem=None, ht=0, bt=2):
    return {
        "kod": kod, "unvan": unvan or kod, "muh_kod": muh,
        "hareket_tipi": ht, "baglanti_tipi": bt,
        "tip": tip, "vade": vade, "tutar": tutar,
        "tutar_donem": tutar if donem is None else donem,
    }


def _veri():
    return [
        # Müşteri A (120) — iki satış, kısmi tahsilat → FIFO eski borçtan düşer
        _row("A", "120.01", 0, "2025-10-01", 100000, unvan="A Ltd"),
        _row("A", "120.01", 0, "2025-12-15", 50000, unvan="A Ltd"),
        _row("A", "120.01", 1, "2025-06-01", 60000, unvan="A Ltd"),
        # Satıcı B (320) — bir alış, kısmi ödeme → kalan borç ileri vadeli
        _row("B", "320.01", 1, "2026-02-01", 80000, unvan="B AŞ"),
        _row("B", "320.01", 0, "2025-07-01", 30000, unvan="B AŞ"),
        # Müşteri C — fazla tahsilat → avans (net 0, yaşlandırmaya girmez)
        _row("C", "120.02", 0, "2025-11-01", 20000, unvan="C San"),
        _row("C", "120.02", 1, "2025-11-05", 30000, unvan="C San"),
    ]


class TestTahsilatAlacak(unittest.TestCase):
    def setUp(self):
        self.ta = build_tahsilat_alacak(_veri(), bas="2025-01-01", bit="2025-12-31")

    def test_toplamlar(self):
        self.assertAlmostEqual(self.ta.alacak_toplam, 90000, places=2)
        self.assertAlmostEqual(self.ta.borc_toplam, 50000, places=2)
        self.assertAlmostEqual(self.ta.net_pozisyon, 40000, places=2)
        self.assertAlmostEqual(self.ta.musteri_avans, 10000, places=2)
        self.assertEqual(self.ta.cari_sayisi, 2)  # A ve B; C net 0

    def test_fifo_yaslandirma(self):
        # 100000 satışın 60000'i kapandı → 40000 açık, vade 2025-10-01 (91 gün gecikmiş = 90+)
        self.assertAlmostEqual(self.ta.alacak_aging[AGING_KOVALAR[4]], 40000, places=2)
        # 50000 satış açık, vade 2025-12-15 (16 gün gecikmiş = 1–30)
        self.assertAlmostEqual(self.ta.alacak_aging[AGING_KOVALAR[1]], 50000, places=2)
        self.assertAlmostEqual(self.ta.alacak_gecikmis, 90000, places=2)

    def test_borc_vadesi_gelmemis(self):
        # Satıcı borcu vadesi 2026-02-01 → asof'tan sonra: vadesi gelmemiş, gecikmiş değil
        self.assertAlmostEqual(self.ta.borc_aging[AGING_KOVALAR[0]], 50000, places=2)
        self.assertAlmostEqual(self.ta.borc_gecikmis, 0, places=2)

    def test_vade_takvimi(self):
        nv = self.ta.net_vade()
        # Tüm alacaklar gecikmiş (girecek), borç yok → net = +90000
        self.assertAlmostEqual(nv[VADE_KOVALAR[0]], 90000, places=2)
        # Borç 32 gün sonra → Gelecek ay (31–60g) çıkacak
        self.assertAlmostEqual(self.ta.borc_vade[VADE_KOVALAR[3]], 50000, places=2)

    def test_performans(self):
        self.assertAlmostEqual(self.ta.donem_satis, 170000, places=2)   # A 150k + C 20k
        self.assertAlmostEqual(self.ta.donem_tahsilat, 90000, places=2)  # A 60k + C 30k
        self.assertAlmostEqual(self.ta.donem_alis, 80000, places=2)
        self.assertAlmostEqual(self.ta.donem_odeme, 30000, places=2)
        self.assertAlmostEqual(self.ta.tahsilat_orani, 90000 / 170000 * 100, places=1)
        self.assertIsNotNone(self.ta.dso)
        self.assertIsNotNone(self.ta.dpo)

    def test_top_listeler(self):
        self.assertEqual(self.ta.top_alacak[0].kod, "A")
        self.assertEqual(self.ta.top_borc[0].kod, "B")
        self.assertAlmostEqual(self.ta.top_alacak[0].gecikmis, 90000, places=2)

    def test_sinif_fallback_muh_koy_yok(self):
        # muh_kod boş; baglanti_tipi=1 → satıcı kabul edilir
        rows = [
            _row("X", "", 1, "2026-03-01", 5000, bt=1),
            _row("X", "", 0, "2025-01-01", 1000, bt=1),
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


if __name__ == "__main__":
    unittest.main()
