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
            export_bilanco_pdf(b, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_gelir_tablosu_pdf(self) -> None:
        from ui.gelir_tablosu_pdf import export_gelir_tablosu_pdf
        gt = build_gelir_tablosu(_GT_ROWS, bas="2026-01-01", bit="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gelir_tablosu.pdf"
            export_gelir_tablosu_pdf(gt, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)


if __name__ == "__main__":
    unittest.main()
