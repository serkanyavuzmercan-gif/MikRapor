"""gercek_durum_ayarlar config roundtrip testleri."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config as config_mod
from gercek_durum_ayarlar import GercekDurumAyarlar, load_gercek_durum_ayarlar, save_gercek_durum_ayarlar


class TestGercekDurumAyarlar(unittest.TestCase):
    def test_varsayilan_hidroteknik(self) -> None:
        a = GercekDurumAyarlar.varsayilan()
        self.assertEqual(a.satis_bazi, "sevk")
        self.assertEqual(a.alis_bazi, "fatura")
        self.assertEqual(a.nakit_kaynak, "gl")

    def test_save_mikro_config_korunur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "base_url": "https://x",
                "api_key": "k",
                "firma_kodu": "26",
                "calisma_yili": 2026,
                "kullanici_kodu": "U",
            }), encoding="utf-8")
            with mock.patch.object(config_mod, "config_path", return_value=path):
                save_gercek_durum_ayarlar(GercekDurumAyarlar(alis_bazi="irsaliye"))
                data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["firma_kodu"], "26")
            self.assertEqual(data["gercek_durum"]["alis_bazi"], "irsaliye")
            with mock.patch.object(config_mod, "config_path", return_value=path):
                loaded = load_gercek_durum_ayarlar()
            self.assertEqual(loaded.alis_bazi, "irsaliye")


if __name__ == "__main__":
    unittest.main()
