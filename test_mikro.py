"""
Mikro API istemcisi, config ve kontrat adaptörü için birim testleri.

PyQt6 GEREKTİRMEZ — yalnızca config / mikro_api / mikro_fetch ve mevcut analizörler test edilir.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import config as config_mod
from analyzer import run_monthly_analysis
from bank_parser import STANDARD_BANK_COLUMNS
from config import MikroConfig
from fatura_parser import STANDARD_FATURA_COLUMNS
from mikro_api import (
    MikroAPIError,
    MikroClient,
    build_auth,
    get_row_value,
    parse_sql_first_row,
    parse_sql_rows,
    password_hash,
)
from mikro_fetch import (
    fetch_all,
    rows_to_banka_df,
    rows_to_fatura_df,
    rows_to_muavin_df,
)
from models import AnalizVeriSeti, AylikMaasGirisi
from muavin_parser import STANDARD_MUAVIN_COLUMNS


class TestPasswordHash(unittest.TestCase):
    def test_with_salt(self) -> None:
        beklenen = hashlib.md5("2026-06-23 GIZLI".encode()).hexdigest()
        self.assertEqual(password_hash("GIZLI", today="2026-06-23"), beklenen)

    def test_without_salt(self) -> None:
        beklenen = hashlib.md5("2026-06-23".encode()).hexdigest()
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
                          kullanici_kodu="alper", sifre_gun="tuz")
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


class TestContractAdapter(unittest.TestCase):
    """Adaptörün ürettiği DataFrame'ler parser kontratıyla birebir aynı mı?"""

    def test_muavin_columns(self) -> None:
        df = rows_to_muavin_df([
            {"tarih": "2026-03-05", "hesap_kodu": "770.01", "hesap_adi": "Gider",
             "borc": 1500.0, "alacak": 0.0, "aciklama": "X", "evrak_no": "12"},
            {"tarih": "2026-03-05", "hesap_kodu": "", "borc": 0, "alacak": 0},  # elenir
        ])
        self.assertEqual(list(df.columns), STANDARD_MUAVIN_COLUMNS)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["ana_hesap"], "770")

    def test_fatura_columns_and_filter(self) -> None:
        df = rows_to_fatura_df([
            {"tarih": "2026-03-10", "cari_kodu": "120.001", "stok_kodu": "A.001",
             "miktar": 2, "net_tutar": 200.0},
            {"stok_kodu": "", "miktar": 0, "net_tutar": 0},  # elenir
        ], "satis")
        self.assertEqual(list(df.columns), STANDARD_FATURA_COLUMNS)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["fatura_turu"], "satis")

    def test_banka_columns_and_ic_transfer(self) -> None:
        df = rows_to_banka_df([
            {"tarih": "2026-03-05", "evrak_tipi": "Havale", "borc": 50000, "alacak": 0,
             "cari_kodu": "120.001", "karsi_hesap_ismi": "ABC"},
            {"tarih": "2026-03-06", "evrak_tipi": "Virman", "borc": 0, "alacak": 1000,
             "cari_kodu": "102.002", "karsi_hesap_ismi": "Diğer Banka"},
        ])
        self.assertEqual(list(df.columns), STANDARD_BANK_COLUMNS)
        self.assertEqual(len(df), 2)
        ic = df[df["cari_kodu"] == "102.002"].iloc[0]
        self.assertTrue(bool(ic["ic_transfer"]))

    def test_fetch_all_feeds_analyzer_end_to_end(self) -> None:
        """fetch_all çıktısı analizör tarafından sorunsuz işlenmeli (kontrat ucu uca)."""
        payloads = {
            "MUHASEBE_HAREKETLERI mh\n        LEFT": [  # muavin
                {"tarih": "2026-03-01", "hesap_kodu": "770.01", "hesap_adi": "Gider",
                 "borc": 8000, "alacak": 0, "aciklama": "Kira", "evrak_no": "1"},
            ],
            "sth_tip = 0": [  # alış fatura
                {"tarih": "2026-03-08", "cari_kodu": "320.001", "stok_kodu": "A.001",
                 "miktar": 10, "net_tutar": 1000.0, "fatura_no": "AF-1"},
            ],
            "sth_tip = 1": [  # satış fatura
                {"tarih": "2026-03-12", "cari_kodu": "120.001", "stok_kodu": "A.001",
                 "miktar": 10, "net_tutar": 1600.0, "fatura_no": "SF-1"},
            ],
            "LIKE '102%'": [  # banka
                {"tarih": "2026-03-12", "evrak_tipi": "Tahsilat", "borc": 1600, "alacak": 0,
                 "cari_kodu": "120.001", "karsi_hesap_ismi": "Müşteri"},
            ],
        }

        def transport(url: str, body: str, timeout: float):
            sql = json.loads(body)["SQLSorgu"]
            for needle, rows in payloads.items():
                if needle in sql:
                    return 200, json.dumps({"result": [{"IsError": False, "Data": rows}]})
            return 200, json.dumps({"result": [{"IsError": False, "Data": []}]})

        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        client = MikroClient(cfg, transport=transport, max_attempts=1)

        dfs = fetch_all(client, "2026-03")
        veri = AnalizVeriSeti(
            analiz_ayi="2026-03",
            muavin_df=dfs["muavin"],
            alis_fatura_df=dfs["alis_fatura"],
            satis_fatura_df=dfs["satis_fatura"],
            banka_df=dfs["banka"],
            maas=AylikMaasGirisi(analiz_ayi="2026-03"),
        )
        report = run_monthly_analysis(veri)
        self.assertIsNotNone(report)
        self.assertEqual(report.analiz_ayi, "2026-03")


if __name__ == "__main__":
    unittest.main()
