"""
Mikro API istemcisi ve config için birim testleri (PyQt6 gerektirmez).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import infra.config as config_mod
from infra.config import MikroConfig
from infra.mikro_api import (
    MikroAPIError,
    MikroClient,
    build_auth,
    get_row_value,
    parse_sql_first_row,
    parse_sql_rows,
    password_hash,
)


class TestPasswordHash(unittest.TestCase):
    def test_with_salt(self) -> None:
        beklenen = hashlib.md5(b"2026-06-23 GIZLI").hexdigest()
        self.assertEqual(password_hash("GIZLI", today="2026-06-23"), beklenen)

    def test_without_salt(self) -> None:
        beklenen = hashlib.md5(b"2026-06-23").hexdigest()
        self.assertEqual(password_hash("", today="2026-06-23"), beklenen)

    def test_build_auth_shape(self) -> None:
        cfg = MikroConfig(base_url="https://x", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        auth = build_auth(cfg)
        self.assertEqual(
            set(auth), {"ApiKey", "FirmaKodu", "CalismaYili", "KullaniciKodu", "Sifre"})
        self.assertEqual(auth["CalismaYili"], 2026)
        self.assertEqual(auth["Sifre"], password_hash("S"))


class TestConfigRoundtrip(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self) -> None:
        if self._old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._old_appdata
        self._tmp.cleanup()

    def test_save_then_load(self) -> None:
        cfg = MikroConfig(base_url="https://mikro.local/", api_key="ABC",
                          firma_kodu="26", calisma_yili=2026,
                          kullanici_kodu="testuser", sifre_gun="tuz")
        path = config_mod.save_config(cfg)
        self.assertTrue(Path(path).is_file())
        loaded = config_mod.load_config()
        self.assertEqual(loaded.base_url, "https://mikro.local")  # trailing slash temizlenir
        self.assertEqual(loaded.firma_kodu, "26")
        self.assertEqual(loaded.calisma_yili, 2026)
        self.assertTrue(loaded.is_complete())

    def test_incomplete_reports_missing(self) -> None:
        cfg = MikroConfig(base_url="", api_key="", firma_kodu="", kullanici_kodu="")
        self.assertFalse(cfg.is_complete())
        self.assertIn("Mikro API adresi", cfg.eksik_alanlar())


class TestSqlParsing(unittest.TestCase):
    def test_sqlresult1(self) -> None:
        res = [{"SQLResult1": [{"a": 1}, {"a": 2}]}]
        self.assertEqual(len(parse_sql_rows(res)), 2)

    def test_list_of_dicts(self) -> None:
        res = [{"x": 1}, {"x": 2}]
        self.assertEqual(parse_sql_rows(res), res)

    def test_dict_inner(self) -> None:
        self.assertEqual(parse_sql_rows({"Data": [{"k": "v"}]}), [{"k": "v"}])

    def test_empty(self) -> None:
        self.assertEqual(parse_sql_rows([]), [])
        self.assertIsNone(parse_sql_first_row([]))

    def test_get_row_value_case_insensitive(self) -> None:
        row = {"STO_KOD": "A.001"}
        self.assertEqual(get_row_value(row, "sto_kod"), "A.001")
        self.assertIsNone(get_row_value(row, "yok"))


class TestMikroClient(unittest.TestCase):
    def _client(self, status: int, payload: dict) -> tuple[MikroClient, list]:
        captured: list = []

        def transport(url: str, body: str, timeout: float):
            captured.append((url, json.loads(body)))
            return status, json.dumps(payload)

        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        return MikroClient(cfg, transport=transport, max_attempts=1), captured

    def test_extracts_data(self) -> None:
        client, captured = self._client(200, {"result": [{"IsError": False, "Data": {"ok": 1}}]})
        out = client.sql_veri_oku("SELECT 1")
        self.assertEqual(out, {"ok": 1})
        url, body = captured[0]
        self.assertTrue(url.endswith("/SqlVeriOkuV2"))
        self.assertEqual(body["SQLSorgu"], "SELECT 1")
        self.assertEqual(body["Mikro"]["FirmaKodu"], "26")

    def test_api_error_raises(self) -> None:
        client, _ = self._client(200, {"result": [{"IsError": True, "ErrorMessage": "yetki yok"}]})
        with self.assertRaises(MikroAPIError) as ctx:
            client.sql_veri_oku("SELECT 1")
        self.assertIn("yetki yok", str(ctx.exception))

    def test_http_error_raises(self) -> None:
        client, _ = self._client(500, {"x": 1})
        with self.assertRaises(MikroAPIError):
            client.sql_veri_oku("SELECT 1")


class TestSqlParams(unittest.TestCase):
    def test_iso_tarih_ok(self) -> None:
        from infra.sql_params import iso_tarih

        self.assertEqual(iso_tarih("2026-07-16"), "2026-07-16")

    def test_iso_tarih_rejects_injection(self) -> None:
        from infra.sql_params import iso_tarih

        with self.assertRaises(ValueError):
            iso_tarih("2026-07-16'; DROP TABLE x--")
        with self.assertRaises(ValueError):
            iso_tarih("not-a-date")
        with self.assertRaises(ValueError):
            iso_tarih("2026-13-40")

    def test_firma_kodu_and_sql_string(self) -> None:
        from infra.sql_params import firma_kodu_guvenli, sql_string

        self.assertEqual(firma_kodu_guvenli("01"), "01")
        self.assertEqual(firma_kodu_guvenli("FIRM-A"), "FIRM-A")
        with self.assertRaises(ValueError):
            firma_kodu_guvenli("01'; DROP--")
        with self.assertRaises(ValueError):
            firma_kodu_guvenli("a' OR '1'='1")
        self.assertEqual(sql_string("O'Brien"), "'O''Brien'")

    def test_fetch_mizan_rejects_bad_date(self) -> None:
        from infra.mikro_fetch import fetch_mizan

        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        client = MikroClient(cfg, transport=lambda *a: (200, "{}"), max_attempts=1)
        with self.assertRaises(ValueError):
            fetch_mizan(client, "2026-07-16'; x--")


if __name__ == "__main__":
    unittest.main()
