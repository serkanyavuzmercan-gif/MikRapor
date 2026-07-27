"""Uygulama künyesi — sürüm senkronu ve hata bildirimi bağlantısı."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

from infra.surum import (
    ILETISIM,
    SURUM,
    TELIF,
    hata_bildirim_baglantisi,
    sistem_bilgisi,
)


class TestSurum(unittest.TestCase):
    def test_pyproject_ile_ayni(self) -> None:
        """PyInstaller paketinde pyproject yok; ikisi elle tutuluyor, ayrışmasınlar."""
        icerik = (Path(__file__).resolve().parent / "pyproject.toml").read_text("utf-8")
        eslesme = re.search(r'^version\s*=\s*"([^"]+)"', icerik, re.MULTILINE)
        self.assertIsNotNone(eslesme, "pyproject.toml içinde version bulunamadı")
        self.assertEqual(eslesme.group(1), SURUM)

    def test_surum_bicimi(self) -> None:
        self.assertRegex(SURUM, r"^\d+\.\d+\.\d+$")

    def test_kunye_alanlari(self) -> None:
        self.assertIn("Hidroteknik", TELIF)
        self.assertEqual(ILETISIM, "mikrapor@hidroteknik.com.tr")

    def test_sistem_bilgisi_surumu_tasir(self) -> None:
        bilgi = sistem_bilgisi()
        self.assertIn(SURUM, bilgi)
        self.assertIn("Python", bilgi)

    def test_hata_bildirimi_ortami_hazir_getirir(self) -> None:
        """Kullanıcıdan «hangi sürüm» diye sormak zorunda kalmayalım."""
        bag = hata_bildirim_baglantisi()
        self.assertTrue(bag.startswith(f"mailto:{ILETISIM}?"))
        cozulmus = unquote(bag)
        self.assertIn(SURUM, cozulmus)
        self.assertIn("Hata Bildirimi", cozulmus)
        self.assertIn(sistem_bilgisi(), cozulmus)

    def test_baglantida_ham_bosluk_yok(self) -> None:
        """mailto gövdesi kaçışlanmazsa e-posta istemcisi bağlantıyı yarıda keser."""
        self.assertNotIn(" ", hata_bildirim_baglantisi())
        self.assertNotIn("\n", hata_bildirim_baglantisi())


if __name__ == "__main__":
    unittest.main()
