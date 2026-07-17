"""
PDF dışa aktarım smoke testleri — reportlab kuruluysa çalışır, yoksa atlanır.

Amaç derin doğrulama değil; PDF üretiminin uçtan uca patlamadığını ve geçerli
bir PDF dosyası (%PDF imzalı, boş olmayan) yazdığını garanti etmek.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import reportlab  # noqa: F401
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False

from domain.gelir_tablosu import build_gelir_tablosu
from domain.mizan_bilanco import build_bilanco

_MIZAN_ROWS = [
    {"hesap_kodu": "100", "borc": 500.0, "alacak": 0.0},
    {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
    {"hesap_kodu": "120", "borc": 5000.0, "alacak": 0.0},
    {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
    {"hesap_kodu": "500", "borc": 0.0, "alacak": 10000.0},
    {"hesap_kodu": "600", "borc": 0.0, "alacak": 1500.0},
]

_GT_ROWS = [
    {"hesap_kodu": "600", "borc": 0.0, "alacak": 42000.0},
    {"hesap_kodu": "610", "borc": 2000.0, "alacak": 0.0},
    {"hesap_kodu": "621", "borc": 30000.0, "alacak": 0.0},
    {"hesap_kodu": "632", "borc": 4000.0, "alacak": 0.0},
    {"hesap_kodu": "660", "borc": 500.0, "alacak": 0.0},
]


def _pdf_dogrula(tc: unittest.TestCase, path: Path) -> None:
    tc.assertTrue(path.is_file())
    data = path.read_bytes()
    tc.assertGreater(len(data), 1000, "PDF şüpheli derecede küçük")
    tc.assertTrue(data.startswith(b"%PDF"), "geçerli PDF imzası yok")


@unittest.skipUnless(_REPORTLAB, "reportlab kurulu değil")
class TestPdfSmoke(unittest.TestCase):
    def test_bilanco_pdf(self) -> None:
        from ui.bilanco_pdf import export_bilanco_pdf
        b = build_bilanco(_MIZAN_ROWS, asof="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bilanco.pdf"
            export_bilanco_pdf(
                b, out, firma="Test Ticaret A.Ş.",
                bas="2026-01-01", bit="2026-06-30",
            )
            _pdf_dogrula(self, out)

    def test_gelir_tablosu_pdf(self) -> None:
        from ui.gelir_tablosu_pdf import export_gelir_tablosu_pdf
        gt = build_gelir_tablosu(_GT_ROWS, bas="2026-01-01", bit="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gelir_tablosu.pdf"
            export_gelir_tablosu_pdf(gt, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_gercek_durum_pdf(self) -> None:
        from domain.gercek_durum import build_gercek_durum
        from ui.gercek_durum_pdf import export_gercek_durum_pdf
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
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gercek_durum.pdf"
            export_gercek_durum_pdf(gd, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_nakit_akis_pdf(self) -> None:
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_pdf import export_nakit_akis_pdf
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0}],
            bakiye_kapanis_rows=[{"cins": 2, "borc_h": 10000.0, "alacak_h": 0.0, "ban_hesap_tip": 0}],
            donem_delta=3000.0, bas="2026-01-01", bit="2026-06-30",
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "nakit_akis.pdf"
            export_nakit_akis_pdf(na, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_tahsilat_alacak_pdf(self) -> None:
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.tahsilat_alacak_pdf import export_tahsilat_alacak_pdf
        ta = build_tahsilat_alacak([
            {"kod": "120.01", "unvan": "Müşteri A", "muh_kod": "120", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 0, "evrak_tarihi": "2026-01-15",
             "cha_vade": "2026-02-15", "tutar": 10000.0, "tutar_donem": 10000.0},
        ], bas="2026-01-01", bit="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "tahsilat.pdf"
            export_tahsilat_alacak_pdf(ta, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_tahmin_pdf(self) -> None:
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_pdf import export_tahmin_pdf
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-06", baslangic_nakit=100000.0, baz_ciro=500000.0,
            buyume_yuzde=2.0, marj_yuzde=20.0, sabit_gider=50000.0, ufuk_ay=6))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "tahmin.pdf"
            export_tahmin_pdf(t, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_trend_pdf(self) -> None:
        from domain.gercek_durum import AyTrend
        from domain.trend import build_trend
        from ui.trend_pdf import export_trend_pdf
        b = build_bilanco(_MIZAN_ROWS, asof="2026-06-30")
        tr = build_trend(
            aylik=[AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000)],
            bilanco=b, bas="2026-01-01", bit="2026-06-30",
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "trend.pdf"
            export_trend_pdf(tr, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)


if __name__ == "__main__":
    unittest.main()
