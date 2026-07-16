"""
UI smoke testleri — PyQt6 kuruluysa offscreen platformda çalışır, yoksa atlanır.

Amaç piksel doğrulama değil; her rapor görünümünün örnek modelle kurulabildiğini,
ana pencerenin ve ayar diyaloglarının çökmeden oluşturulabildiğini garanti etmek
(CI'da GUI regresyonlarını erken yakalar).
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _PYQT = True
except ImportError:
    _PYQT = False


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestUiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    # ------------------------------------------------------------ görünümler
    def test_bilanco_view(self) -> None:
        from domain.mizan_bilanco import build_bilanco
        from ui.bilanco_view import build_bilanco_widget
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 5000.0},
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 1000.0},
        ], asof="2026-06-30")
        w = build_bilanco_widget(b, firma="Test A.Ş.")
        self.assertIsNotNone(w)

    def test_gelir_tablosu_view(self) -> None:
        from domain.gelir_tablosu import build_gelir_tablosu
        from ui.gelir_tablosu_view import build_gelir_tablosu_widget
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 42000.0},
            {"hesap_kodu": "621", "borc": 30000.0, "alacak": 0.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertIsNotNone(build_gelir_tablosu_widget(gt, firma="Test A.Ş."))

    def test_gercek_durum_view(self) -> None:
        from domain.gercek_durum import build_gercek_durum
        from ui.gercek_durum_view import build_gercek_durum_widget
        gd = build_gercek_durum(
            stok_rows=[
                {"sth_tip": 1, "sth_evraktip": 4, "tutar": 42000.0, "miktar": 10, "adet": 3},
                {"sth_tip": 0, "sth_evraktip": 3, "tutar": 30000.0, "miktar": 8, "adet": 2},
            ],
            stok_aylik=[{"ay": "2026-01", "sth_tip": 1, "sth_evraktip": 4, "tutar": 42000.0}],
            nakit_rows=[{"giren": 50000.0, "cikan": 30000.0}],
            nakit_aylik=[{"ay": "2026-01", "giren": 50000.0, "cikan": 30000.0}],
            bas="2026-01-01", bit="2026-06-30",
        )
        self.assertIsNotNone(build_gercek_durum_widget(gd, firma="Test A.Ş."))

    def test_tahsilat_alacak_view(self) -> None:
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.tahsilat_alacak_view import build_tahsilat_alacak_widget
        ta = build_tahsilat_alacak([
            {"kod": "120.01", "unvan": "Müşteri A", "muh_kod": "120", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 0, "evrak_tarihi": "2026-01-15",
             "cha_vade": "2026-02-15", "tutar": 10000.0, "tutar_donem": 10000.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertIsNotNone(build_tahsilat_alacak_widget(ta, firma="Test A.Ş."))

    def test_nakit_akis_view(self) -> None:
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_view import build_nakit_akis_widget
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0}],
            bakiye_kapanis_rows=[{"cins": 2, "borc_h": 10000.0, "alacak_h": 0.0, "ban_hesap_tip": 0}],
            donem_delta=3000.0, bas="2026-01-01", bit="2026-06-30",
        )
        self.assertIsNotNone(build_nakit_akis_widget(na, firma="Test A.Ş."))

    def test_tahmin_view(self) -> None:
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import build_tahmin_widget
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-06", baslangic_nakit=100000.0, baz_ciro=500000.0,
            buyume_yuzde=2.0, marj_yuzde=20.0, sabit_gider=50000.0, ufuk_ay=6))
        self.assertIsNotNone(build_tahmin_widget(t, firma="Test A.Ş."))

    def test_trend_view(self) -> None:
        from domain.gercek_durum import AyTrend
        from domain.mizan_bilanco import build_bilanco
        from domain.trend import build_trend
        from ui.trend_view import build_trend_widget
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 6000.0},
        ], asof="2026-06-30")
        tr = build_trend(
            aylik=[AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000)],
            bilanco=b, bas="2026-01-01", bit="2026-06-30",
        )
        self.assertIsNotNone(build_trend_widget(tr, firma="Test A.Ş."))

    # ------------------------------------------------- pencere ve diyaloglar
    def test_ana_pencere(self) -> None:
        from ui.app import MikRaporWindow
        w = MikRaporWindow()
        try:
            self.assertEqual(w._tabs.count(), 7)  # 7 rapor sekmesi
        finally:
            w.close()

    def test_ayar_diyaloglari(self) -> None:
        from ui.gercek_durum_settings_dialog import GercekDurumAyarlarDialog
        from ui.mikro_settings_dialog import MikroAyarlarDialog
        MikroAyarlarDialog()
        GercekDurumAyarlarDialog()


if __name__ == "__main__":
    unittest.main()
