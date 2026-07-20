"""domain.terimler sade-dil sözlüğü için birim testleri (PyQt6 gerektirmez)."""

from __future__ import annotations

import unittest

from domain.mizan_bilanco import build_bilanco
from domain.terimler import SADE_ORAN, sade_oran, sade_terim
from domain.trend import build_trend


class TestTerimler(unittest.TestCase):
    def test_sade_oran_var(self):
        for kod in ("cari", "asit", "nakit_oran", "borc_oz", "oz_oran", "kv_oran", "donen_oran"):
            self.assertTrue(sade_oran(kod), f"{kod} için sade açıklama yok")
        self.assertEqual(sade_oran("bilinmeyen"), "")

    def test_sade_oran_formul_tekrari_degil(self):
        # Açıklama "ne işe yarar" olmalı; ham formül ("/") olmamalı.
        for metin in SADE_ORAN.values():
            self.assertNotIn(" / ", metin)

    def test_sade_terim_harf_duyarsiz(self):
        self.assertTrue(sade_terim("kvyk"))
        self.assertEqual(sade_terim("KVYK"), sade_terim("kvyk"))
        self.assertEqual(sade_terim("yok-böyle"), "")

    def test_build_trend_sade_aciklama_kullanir(self):
        # build_trend oranlarının açıklaması artık sade dilde (formül değil).
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 10000, "alacak": 0},
            {"hesap_kodu": "320", "borc": 0, "alacak": 4000},
            {"hesap_kodu": "500", "borc": 0, "alacak": 6000},
        ], asof="2026-06-30")
        tr = build_trend(aylik=[], bilanco=b, bas="2026-01-01", bit="2026-06-30")
        cari = next(o for o in tr.oranlar if o.kod == "cari")
        self.assertEqual(cari.aciklama, sade_oran("cari"))
        self.assertNotIn("/", cari.aciklama)


if __name__ == "__main__":
    unittest.main()
