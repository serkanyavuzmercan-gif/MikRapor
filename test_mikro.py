"""
Mikro API istemcisi ve config için birim testleri (PyQt6 gerektirmez).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
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
    def test_firma_kodu_liste_ve_araliktan_turetilir(self) -> None:
        cfg = MikroConfig(
            base_url="https://x", api_key="K", firma_kodlari="001-100",
            calisma_yili=2026, kullanici_kodu="U", sifre_gun="S",
        ).normalized()
        self.assertEqual(cfg.firma_kodu, "001")
        self.assertTrue(cfg.is_complete())

    def test_calisma_yili_bosken_baglanti_icin_bugun_kullanilir(self) -> None:
        cfg = MikroConfig(calisma_yili=0).normalized()
        from datetime import date
        self.assertEqual(cfg.calisma_yili, date.today().year)

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

    def test_yerel_tarih_kullanilir(self) -> None:
        """
        UTC kullanılıyordu; Türkiye UTC+3 olduğu için yerel gece yarısından sonra UTC
        hâlâ önceki günü gösteriyor ve Mikro «Şifre Hatalı!» diyordu. Program her gece
        00:00–03:00 arası çalışmaz oluyordu (canlıda birebir görüldü).
        """
        from datetime import datetime
        yerel = datetime.now().strftime("%Y-%m-%d")  # noqa: DTZ005
        self.assertEqual(password_hash("S"), password_hash("S", today=yerel))

    def test_gun_adaylari_yerelle_baslar(self) -> None:
        from datetime import datetime

        from infra.mikro_api import gun_adaylari
        adaylar = gun_adaylari()
        self.assertEqual(adaylar[0], datetime.now().strftime("%Y-%m-%d"))  # noqa: DTZ005
        self.assertLessEqual(len(adaylar), 2)
        self.assertEqual(len(adaylar), len(set(adaylar)))   # aynı günü iki kez deneme


class TestSifreGunuYedegi(unittest.TestCase):
    """Yerel tarih reddedilirse UTC ile bir kez daha denenmeli (sunucu saati farklı olabilir)."""

    @staticmethod
    def _cfg() -> MikroConfig:
        return MikroConfig(base_url="https://x", api_key="K", firma_kodu="26",
                           calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")

    def _client(self, transport):
        from infra.mikro_api import MikroClient
        return MikroClient(self._cfg(), transport=transport)

    def test_sifre_hatasinda_ikinci_gun_denenir(self) -> None:
        from unittest.mock import patch

        from infra.mikro_api import build_auth
        gonderilen: list[str] = []

        def transport(url, body, timeout):
            gonderilen.append(json.loads(body)["Mikro"]["Sifre"])
            if len(gonderilen) == 1:
                return 200, json.dumps({"result": [
                    {"IsError": True, "ErrorMessage": "Şifre Hatalı!"}]})
            return 200, json.dumps({"result": [{"IsError": False, "Data": "tamam"}]})

        with patch("infra.mikro_api.gun_adaylari", return_value=["2026-07-28", "2026-07-27"]):
            sonuc = self._client(transport).request("X", {"Mikro": build_auth(self._cfg())})

        self.assertEqual(sonuc, "tamam")
        self.assertEqual(len(gonderilen), 2)
        self.assertEqual(gonderilen[0], password_hash("S", today="2026-07-28"))
        self.assertEqual(gonderilen[1], password_hash("S", today="2026-07-27"))

    def test_sifre_disi_hatada_tekrar_denenmez(self) -> None:
        """Yalnız parola reddinde gün değiştirilir; başka hatada boşuna istek atılmaz."""
        from unittest.mock import patch

        from infra.mikro_api import MikroAPIError, build_auth
        cagri = []

        def transport(url, body, timeout):
            cagri.append(1)
            return 200, json.dumps({"result": [
                {"IsError": True, "ErrorMessage": "Tablo bulunamadı"}]})

        with patch("infra.mikro_api.gun_adaylari", return_value=["2026-07-28", "2026-07-27"]):
            with self.assertRaises(MikroAPIError):
                self._client(transport).request("X", {"Mikro": build_auth(self._cfg())})
        self.assertEqual(len(cagri), 1)


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
        cfg = MikroConfig(base_url="", api_key="", firma_kodu="", kullanici_kodu="", sifre_gun="")
        self.assertFalse(cfg.is_complete())
        self.assertIn("Mikro API adresi", cfg.eksik_alanlar())
        self.assertIn("Şifre", cfg.eksik_alanlar())

    def test_sifre_zorunlu(self) -> None:
        cfg = MikroConfig(
            base_url="https://x.example/api", api_key="k", firma_kodu="01",
            kullanici_kodu="U", sifre_gun="",
        )
        self.assertFalse(cfg.is_complete())
        self.assertEqual(cfg.eksik_alanlar(), ["Şifre"])


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


class TestZamanAsimiMesaji(unittest.TestCase):
    """
    Mikro yanıt vermeyince kullanıcı NE YAPACAĞINI bilmeli.

    Kullanıcı «bazen çok uzun sürüyor, mikro cevap vermiyor olabilir; bu gibi durumda
    hataları anlayıp hata verecek bir sistem lazım» dedi. Eskiden ekrana ham soket
    metni («The read operation timed out») çıkıyordu — ne olduğu da ne yapılacağı da
    belirsizdi.
    """

    def _client(self, hata: Exception) -> MikroClient:
        def transport(url: str, body: str, timeout: float):
            raise hata

        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        return MikroClient(cfg, transport=transport, max_attempts=1, timeout=180.0)

    def test_zaman_asimi_ayri_sinif(self) -> None:
        from infra.mikro_api import MikroZamanAsimiError
        with self.assertRaises(MikroZamanAsimiError) as ctx:
            self._client(TimeoutError("timed out")).sql_veri_oku("SELECT 1")
        mesaj = str(ctx.exception)
        self.assertIn("Mikro yanıt vermedi", mesaj)
        self.assertIn("180", mesaj)                 # kaç saniye beklendi
        self.assertIn("daraltıp", mesaj)            # ne yapılacağı

    def test_zaman_asimi_da_mikro_hatasidir(self) -> None:
        """Sekmelerdeki «except MikroAPIError» yolları bozulmamalı."""
        with self.assertRaises(MikroAPIError):
            self._client(TimeoutError("timed out")).sql_veri_oku("SELECT 1")

    def test_diger_ag_hatasi_eski_mesajla_kalir(self) -> None:
        from infra.mikro_api import MikroZamanAsimiError
        with self.assertRaises(MikroAPIError) as ctx:
            self._client(ConnectionRefusedError("refused")).sql_veri_oku("SELECT 1")
        self.assertNotIsInstance(ctx.exception, MikroZamanAsimiError)
        self.assertIn("bağlantı hatası", str(ctx.exception))


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


class TestBaseUrl(unittest.TestCase):
    def test_https_ok(self) -> None:
        from infra.config import base_url_dogrula

        self.assertEqual(base_url_dogrula("https://192.168.1.50:443"), [])

    def test_http_localhost_ok(self) -> None:
        from infra.config import base_url_dogrula

        self.assertEqual(base_url_dogrula("http://localhost:8080"), [])
        self.assertEqual(base_url_dogrula("http://127.0.0.1"), [])

    def test_http_remote_rejected(self) -> None:
        from infra.config import base_url_dogrula

        hatalar = base_url_dogrula("http://192.168.1.50")
        self.assertTrue(hatalar)
        self.assertTrue(any("https" in h.lower() for h in hatalar))

    def test_scheme_required(self) -> None:
        from infra.config import base_url_dogrula

        self.assertTrue(base_url_dogrula("192.168.1.50:443"))


class TestGizliLocal(unittest.TestCase):
    def test_roundtrip(self) -> None:
        from infra import gizli

        orijinal = "gizli-api-anahtari-123"
        sifreli = gizli.sifrele(orijinal)
        self.assertTrue(sifreli.startswith("local:") or sifreli.startswith("dpapi:"))
        self.assertNotEqual(sifreli, orijinal)
        self.assertEqual(gizli.coz(sifreli), orijinal)

    def test_plaintext_passthrough(self) -> None:
        from infra import gizli

        self.assertEqual(gizli.coz("duz-metin"), "duz-metin")


class TestCancelToken(unittest.TestCase):
    def test_iptal_mi(self) -> None:
        from infra.cancel import CancelToken, aktif_iptal, iptal_baglam

        t = CancelToken()
        self.assertFalse(t.iptal_mi())
        t.iptal()
        self.assertTrue(t.iptal_mi())
        with iptal_baglam(t):
            self.assertIs(aktif_iptal(), t)
        self.assertIsNone(aktif_iptal())


class _SqlYakala:
    """sql_veri_oku'yu yakalayan sahte istemci — kurulan SQL doğrulanabilsin."""

    def __init__(self) -> None:
        self.sorgular: list[str] = []
        self.cfg = MikroConfig(
            base_url="https://ornek.local", api_key="k", firma_kodu="20",
            calisma_yili=2025, kullanici_kodu="u", sifre_gun="s")

    def sql_veri_oku(self, sql: str, **_kw) -> dict:
        self.sorgular.append(sql)
        return {"Data": []}


class TestStokEvraktipTeshis(unittest.TestCase):
    """
    Şüpheli bir hareket türünü açan teşhis sorguları.

    Canlıda tip=0/evraktip=12 satır başına ~238 milyon TL veriyordu; bu sorgular
    o toplamın birkaç bozuk kayıttan mı yoksa alanın anlamından mı geldiğini ayırır.
    """

    def test_yillik_tip_ve_evraktipi_suzer(self) -> None:
        from infra.mikro_fetch import fetch_stok_evraktip_yillik
        c = _SqlYakala()
        fetch_stok_evraktip_yillik(c, "2021-01-01", "2025-12-31", 0, 12)
        sql = c.sorgular[0]
        self.assertIn("sth_tip = 0 AND sth_evraktip = 12", sql)
        self.assertIn("MAX(sth_tutar)", sql)          # aykırı satır görünsün
        self.assertIn(">= '2021-01-01'", sql)
        self.assertIn("< '2026-01-01'", sql)          # bitiş günü tam dahil

    def test_tepe_satirlar_buyukten_kucuge(self) -> None:
        from infra.mikro_fetch import fetch_stok_evraktip_tepe
        c = _SqlYakala()
        fetch_stok_evraktip_tepe(c, "2021-01-01", "2025-12-31", 1, 0, adet=5)
        sql = c.sorgular[0]
        self.assertIn("TOP 5", sql)
        self.assertIn("ORDER BY sth_tutar DESC", sql)
        self.assertIn("sth_tip = 1 AND sth_evraktip = 0", sql)

    def test_tip_evraktip_sayiya_zorlanir(self) -> None:
        """tip/evraktip SQL'e gömülüyor — metin geçirilirse enjeksiyon olurdu."""
        from infra.mikro_fetch import fetch_stok_evraktip_yillik
        c = _SqlYakala()
        with self.assertRaises(ValueError):
            fetch_stok_evraktip_yillik(c, "2021-01-01", "2025-12-31", "0; DROP TABLE x--", 12)

    def test_tepe_adedi_sinirli(self) -> None:
        from infra.mikro_fetch import fetch_stok_evraktip_tepe
        c = _SqlYakala()
        fetch_stok_evraktip_tepe(c, "2021-01-01", "2025-12-31", 0, 12, adet=10_000)
        self.assertIn("TOP 100", c.sorgular[0])


class TestStokMaliyetTeshis(unittest.TestCase):
    """
    Maliyet kolonu kullanılabilir mi? — kolon VAR demek yeterli değil.

    Kapanış fişi işlenmeden brüt kâr göstermek için satış satırının kendi maliyetini
    taşıması gerekiyor. İki şey ölçülmeden kolon bağlanamaz: dolu mu (maliyet
    güncellemesi çalışmamışsa 0'dır, 0'ı maliyet sanmak marjı %100 gösterir) ve
    birim maliyet mi satır toplamı mı (yanlış yorum brüt kârı miktar katı şişirir).
    """

    def test_uc_kolon_da_iki_yorumla_olculur(self) -> None:
        from infra.mikro_fetch import fetch_stok_maliyet_teshis
        c = _SqlYakala()
        fetch_stok_maliyet_teshis(c, "2026-01-01", "2026-07-28")
        sql = c.sorgular[0]
        for ad in ("ana", "alternatif", "orjinal"):
            self.assertIn(f"SUM(sth_maliyet_{ad}) AS {ad}_duz", sql)
            self.assertIn(f"SUM(sth_maliyet_{ad} * sth_miktar) AS {ad}_carpim", sql)
            self.assertIn(f"WHEN sth_maliyet_{ad} <> 0", sql)   # doluluk sayımı

    def test_evraktipe_kadar_kirilir(self) -> None:
        """
        Doluluk evrak tipi bazında ölçülmeli.

        Canlıda tip=1 satırlarının %89'u doluydu ve kolon «kullanılamaz» görünüyordu.
        Oysa maliyetsiz satır satış değil sarf/depo fişi olabilir; gerçek satış
        evrakları (irsaliye/fatura) ayrı ölçülmeden kolon haksız yere çöpe atılır.
        """
        from infra.mikro_fetch import fetch_stok_maliyet_teshis
        c = _SqlYakala()
        fetch_stok_maliyet_teshis(c, "2026-01-01", "2026-07-28")
        sql = c.sorgular[0]
        grup = sql.split("GROUP BY")[1]
        self.assertIn("sth_tip", grup)
        self.assertIn("CONVERT(char(7)", sql)
        self.assertIn("sth_evraktip", grup)
        self.assertIn("SUM(sth_tutar) AS tutar", sql)
        self.assertIn(">= '2026-01-01'", sql)
        self.assertIn("< '2026-07-29'", sql)          # bitiş günü tam dahil


class TestFaturalasmaTeshis(unittest.TestCase):
    """
    İrsaliye + fatura toplanınca satış iki kez mi sayılıyor?

    Kullanıcının iş akışı: önce irsaliye, sonra carinin bekleyen irsaliyeleri toplu
    faturalaşıyor; irsaliye satırı silinmiyor. Faturalaştırma AYRI stok hareketi
    yaratıyorsa toplam mükerrer, mevcut satırı damgalayıp geçiyorsa toplam doğru.
    Kararı satır sayısı tahminiyle değil `sth_fat_uid` damgasıyla veriyoruz.
    """

    def test_damga_dolu_bos_diye_ayrilir(self) -> None:
        from infra.mikro_fetch import fetch_stok_faturalasma
        c = _SqlYakala()
        fetch_stok_faturalasma(c, "2026-01-01", "2026-07-28")
        sql = c.sorgular[0]
        self.assertIn("sth_fat_uid", sql)
        self.assertIn("AS faturalandi", sql)
        self.assertIn("00000000-0000-0000-0000-000000000000", sql)   # boş GUID = damgasız
        self.assertIn("sth_fat_uid IS NULL", sql)                    # NULL da damgasız
        grup = sql.split("GROUP BY")[1]
        self.assertIn("sth_evraktip", grup)
        self.assertIn("sth_fat_uid", grup)                           # damga kırılımda


class TestFaturaOrtakligi(unittest.TestCase):
    """
    Fatura satırları irsaliyelerin KOPYASI mı, ayrı satışlar mı?

    Damgalama modeli anlaşıldıktan sonra kalan tek soru buydu: canlıda 262 fatura
    satırı 1,1 milyon TL taşıyor (satışın %5,3'ü) — kopyaysa o kadarı iki kez
    sayılıyor. Kesişimi JOIN'siz ölçüyoruz; self-join dev tabloyu taratabilirdi.
    """

    def test_kesisim_joinsiz_olculur(self) -> None:
        from infra.mikro_fetch import fetch_stok_fatura_ortakligi
        c = _SqlYakala()
        fetch_stok_fatura_ortakligi(c, "2026-01-01", "2026-07-28")
        sql = c.sorgular[0]
        self.assertNotIn("JOIN", sql.upper())
        self.assertIn("AS irsaliye_fatura", sql)
        self.assertIn("AS fatura_fatura", sql)
        self.assertIn("AS birlesik_fatura", sql)
        self.assertIn("sth_evraktip IN (1, 4)", sql)


class TestMaliyetHukmu(unittest.TestCase):
    """
    Hüküm mantığı — canlı rakamlarla.

    İki tuzak vardı: (1) boşluk her aya dağılmışken «maliyet güncellemesi geç kaldı»
    demek, (2) aykırı bir kolonun (canlıda «orjinal» 5,2 milyon) gerçek mutabakatı
    (ana 11,7M · alternatif 12,1M) gizlemesi ve alt sınırı aşağı çekmesi.
    """

    _OLCUM = [("ana", "satır toplamı", 11_698_209.18, 42.9),
              ("alternatif", "birim × miktar", 12_119_498.15, 40.8),
              ("orjinal", "satır toplamı", 5_177_027.23, 74.7)]

    def test_aykiri_kolon_mutabakati_bozmaz(self) -> None:
        from stok_diag_cli import _uyusan_kume
        kume = _uyusan_kume(self._OLCUM)
        self.assertEqual([k[0] for k in kume], ["ana", "alternatif"])
        self.assertEqual(min(o[2] for o in kume), 11_698_209.18)   # alt sınır aykırıdan değil

    def test_tek_basina_kalan_kolon_mutabakat_saymaz(self) -> None:
        from stok_diag_cli import _uyusan_kume
        self.assertEqual(len(_uyusan_kume([self._OLCUM[2]])), 1)

    def test_dagilmis_bosluk_zamanlama_sorunu_sayilmaz(self) -> None:
        import contextlib
        import io

        from stok_diag_cli import _maliyet_hukmu
        aylik = {"2026-01": [2411, 1980], "2026-02": [2100, 1910], "2026-03": [2748, 2501],
                 "2026-04": [2706, 2448], "2026-05": [2366, 2110], "2026-06": [3260, 2981],
                 "2026-07": [2585, 2328]}
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            _maliyet_hukmu(aylik, self._OLCUM, 20_481_407.46, 18176)
        metin = cikti.getvalue()
        self.assertIn("HER AYA dağılmış", metin)
        self.assertNotIn("Maliyet Güncelleme", metin)     # sebep zamanlama DEĞİL
        self.assertIn("MUTABAKAT", metin)
        self.assertIn("11.698.209,18", metin)             # alt sınır uyuşan kümeden

    def test_son_aylarda_toplanan_bosluk_zamanlama_sorunudur(self) -> None:
        import contextlib
        import io

        from stok_diag_cli import _maliyet_hukmu
        aylik = {"2026-01": [1000, 1000], "2026-02": [1000, 1000], "2026-03": [1000, 1000],
                 "2026-04": [1000, 1000], "2026-05": [1000, 990], "2026-06": [1000, 200],
                 "2026-07": [1000, 0]}
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            _maliyet_hukmu(aylik, self._OLCUM, 20_481_407.46, 7000)
        self.assertIn("Maliyet Güncelleme", cikti.getvalue())


class TestStokBakiyeHukmu(unittest.TestCase):
    """
    Canlı stok değeri mizanın yerine geçebilir mi? — ölçmeden EVET denmemeli.

    Canlıda tek bir doluluk oranına (%91,3) bakılıp yeşil ışık yakılıyordu. İki şey
    ölçülmemişti:

    1. KAPSAM. Stok seviyesi kümülatiftir ve Mikro yılları ayrı veritabanlarına böler.
       Firma 26'nın stok tablosu 2025-01-10'da başlıyor, geçmiş firma 20'de. Tek
       veritabanının kümülatifi seviye değildir; kataloğun tamamı okunmalı ve pencereler
       ÇAKIŞMAMALI (2025 iki veritabanında birden var).
    2. EKSİK MALİYETİN YÖNÜ. Eksik bir çıkış satırı stoğu tam da mizandaki gibi şişirir;
       yönü bilmeden verilen karar hatayı düzeltmek yerine kopyalar.
    """

    @staticmethod
    def _yaz(fn, *args) -> str:
        import contextlib
        import io
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            fn(*args)
        return cikti.getvalue()

    _CFG = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                       calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")

    # Canlı kurulum: firma 20 → 2020-2025, firma 26 → 2025-2026.
    _KAPSAM_2020 = {"ilk": "2020-02-03", "adet": 96_000}
    _KAPSAM_2026 = {"ilk": "2025-01-10", "adet": 28_078}
    _BAKIYE_2020 = {"adet": 96_000, "maliyet_dolu": 88_000, "miktar": 120_000.0,
                    "maliyet": 6_000_000.0, "tutar": 5_000_000.0,
                    "aykiri_satir": 0, "aykiri_maliyet": 0.0,
                    "temiz_maliyet": 6_000_000.0, "temiz_miktar": 120_000.0}
    _BAKIYE_2026 = {"adet": 28_078, "maliyet_dolu": 25_635, "miktar": 276_129.45,
                    "maliyet": 22_790_157.10, "tutar": 17_399_874.13,
                    "aykiri_satir": 0, "aykiri_maliyet": 0.0,
                    "temiz_maliyet": 22_790_157.10, "temiz_miktar": 276_129.45}
    # Canlıdaki bozuk kayıt: 2 adet mala 3,3 trilyon TL (07.12.2023, yevmiye 731).
    _BAKIYE_BOZUK = dict(_BAKIYE_2020, aykiri_satir=1,
                         aykiri_maliyet=3_333_333_333_340.0,
                         maliyet=3_339_333_333_340.0)
    # Boş satırların çoğu ÇIKIŞTA: canlı rakam mizanla AYNI yönde şişik (canlı durum).
    _YON_CIKISTA = [
        {"tip": 0, "bos_satir": 384, "bos_miktar": 8_801.33,
         "dolu_satir": 12_000, "dolu_miktar": 300_000.0, "dolu_maliyet": 25_902_000.0},
        {"tip": 1, "bos_satir": 2_055, "bos_miktar": 21_159.66,
         "dolu_satir": 13_600, "dolu_miktar": 280_000.0, "dolu_maliyet": 29_402_800.0},
    ]
    _YON_DENGELI = [
        {"tip": 0, "bos_satir": 90, "bos_miktar": 900.0,
         "dolu_satir": 12_000, "dolu_miktar": 300_000.0, "dolu_maliyet": 30_000_000.0},
        {"tip": 1, "bos_satir": 95, "bos_miktar": 880.0,
         "dolu_satir": 13_600, "dolu_miktar": 280_000.0, "dolu_maliyet": 28_000_000.0},
    ]

    def _calistir(self, *, kapsamlar, parcalar, bakiyeler, yon) -> str:
        """`parcalar`: [(firma_kodu, bas, bit)] — donem_parcalari'nin döndürdüğü bölme."""
        from unittest.mock import patch

        import stok_diag_cli as cli
        from infra.veritabani import FirmaKapsami

        def _client(kod: str):
            return MikroClient(replace(self._CFG, firma_kodu=kod),
                               transport=lambda *a: (200, "{}"), max_attempts=1)

        clientlar = {kod: _client(kod) for kod, _, _ in parcalar}
        yamalar = [
            patch.object(cli, "katalog", return_value=[
                FirmaKapsami(kod, ilk, son) for kod, ilk, son in kapsamlar]),
            patch.object(cli, "donem_parcalari",
                         return_value=[(clientlar[k], b, e) for k, b, e in parcalar]),
            patch.object(cli, "fetch_stok_kapsam",
                         side_effect=lambda c, *_a, **_k: [kapsamlar_veri[c.cfg.firma_kodu]]),
            patch.object(cli, "fetch_stok_bakiye_teshis",
                         side_effect=lambda c, *_a, **_k: [bakiyeler[c.cfg.firma_kodu]]),
            patch.object(cli, "fetch_stok_maliyet_yonu",
                         side_effect=lambda c, *_a, **_k: yon[c.cfg.firma_kodu]),
            patch.object(cli, "_dene_mizan", return_value=21_498_296.17),
        ]
        kapsamlar_veri = {"20": self._KAPSAM_2020, "26": self._KAPSAM_2026}
        for y in yamalar:
            y.start()
        try:
            return self._yaz(cli._bakiye_teshisi, clientlar["26"], self._CFG, "2026-07-28")
        finally:
            for y in yamalar:
                y.stop()

    def _iki_veritabani(self, yon26) -> str:
        return self._calistir(
            kapsamlar=[("20", 2020, 2025), ("26", 2025, 2026)],
            # 2025 İKİ veritabanında birden var; pencereler çakışmadan bölünür.
            parcalar=[("20", "2020-01-01", "2025-12-31"),
                      ("26", "2026-01-01", "2026-07-28")],
            bakiyeler={"20": self._BAKIYE_2020, "26": self._BAKIYE_2026},
            yon={"20": self._YON_DENGELI, "26": yon26})

    def _tek_veritabani(self, yon26) -> str:
        """Canlı 2026 rakamları — hükmün eşiği bu ölçekte sınanır."""
        return self._calistir(
            kapsamlar=[("26", 2026, 2026)],
            parcalar=[("26", "2026-01-01", "2026-07-28")],
            bakiyeler={"26": self._BAKIYE_2026},
            yon={"26": yon26})

    def test_butun_veritabanlari_toplanir(self) -> None:
        """Seviye tek veritabanından çıkmaz; katalogtaki her yıl okunur."""
        metin = self._iki_veritabani(self._YON_DENGELI)
        self.assertIn("firma   20", metin)
        self.assertIn("firma   26", metin)
        # 96.000 + 28.078 satır, 6.000.000 + 22.790.157,10 maliyet
        self.assertIn("124.078", metin)
        self.assertIn("28.790.157,10", metin)

    def test_bos_satirlar_cikistaysa_baglanmaz(self) -> None:
        """
        Eksik çıkış satırı stoğu şişirir — mizanın hatasını kopyalamış olurduk.

        Canlı ölçüm: boş satırların 2.055'i çıkışta, 384'ü girişte; net düzeltme
        −1.461.959 TL, yani canlı değerin %6,4'ü. Doluluk %91,3 olduğu hâlde bağlanamaz.
        """
        metin = self._tek_veritabani(self._YON_CIKISTA)
        self.assertIn("→ HAYIR", metin)
        self.assertIn("net etkisi", metin)

    def test_bosluk_dengeliyse_baglanabilir(self) -> None:
        metin = self._iki_veritabani(self._YON_DENGELI)
        self.assertIn("→ EVET", metin)
        self.assertIn("Düzeltilmiş canlı", metin)

    def test_aykiri_satir_varken_hicbir_rakam_baglanmaz(self) -> None:
        """
        Tek bozuk kayıt 390 bin satırın toplamını ele geçiriyor.

        Canlıda net maliyet 3,28 TRİLYON çıktı; 3,3 trilyonluk tek satır yüzünden.
        Aykırı ayrı sayılır, elenen de yazılır — ama düzeltilmeden hüküm verilmez.
        """
        metin = self._calistir(
            kapsamlar=[("20", 2020, 2025), ("26", 2025, 2026)],
            parcalar=[("20", "2020-01-01", "2025-12-31"),
                      ("26", "2026-01-01", "2026-07-28")],
            bakiyeler={"20": self._BAKIYE_BOZUK, "26": self._BAKIYE_2026},
            yon={"20": self._YON_DENGELI, "26": self._YON_DENGELI})
        self.assertIn("Aykırı satır", metin)
        self.assertIn("→ HAYIR", metin)
        self.assertIn("Veri Sağlığı", metin)
        # Temiz rakam aykırıdan arınmış olmalı; ham toplam basılsa 3 trilyon görünürdü.
        self.assertIn("Temiz net maliyet", metin)

    def test_bilinmeyen_yon_kodu_cikis_sayilmaz(self) -> None:
        """
        Canlıda üçüncü bir sth_tip vardı ve tabloda «çıkış» diye İKİ KEZ göründü.

        Yönü bilinmeyen satırın işareti de bilinmez; net düzeltme hesaplanamaz.
        """
        yon = [*self._YON_DENGELI,
               {"tip": 7, "bos_satir": 12, "bos_miktar": 40.0,
                "dolu_satir": 5, "dolu_miktar": 100.0, "dolu_maliyet": 2_954.0}]
        metin = self._tek_veritabani(yon)
        self.assertIn("tip 7 (?)", metin)
        # Tabloda tek bir «çıkış» SATIRI olmalı; bilinmeyen tip çıkış diye sayılmaz.
        satirlar = [s for s in metin.splitlines() if s.strip().startswith("çıkış")]
        self.assertEqual(len(satirlar), 1)
        # GİZLEMİYORUZ: bilinen yönlerden düzeltme hesaplanır, bilinmeyen pay
        # ölçülmüş bir sınır olarak ayrıca yazılır (CLAUDE.md kural 3).
        self.assertIn("Ölçülen net düzeltme", metin)
        self.assertIn("Yönü bilinmeyen pay", metin)

    def test_gecmis_hareket_eksikse_uyarir(self) -> None:
        """Katalog 2020 diyor ama en erken hareket 2025 ise kümülatif eksik olabilir."""
        metin = self._calistir(
            kapsamlar=[("26", 2020, 2026)],
            parcalar=[("26", "2020-01-01", "2026-07-28")],
            bakiyeler={"26": self._BAKIYE_2026},
            yon={"26": self._YON_DENGELI})
        self.assertIn("DİKKAT", metin)
        self.assertIn("kümülatif eksik olabilir", metin)


class TestKrediKartiSorgusu(unittest.TestCase):
    """
    Açık kart borcu sorgusu — dev fiş tablosunu taramamalı.

    Eski hâli hesap ADI süzgecini MUHASEBE_FISLERI'ne iki LEFT JOIN ile uyguluyordu;
    biri `muh_hesap_kod = LEFT(fis_hesap_kod, 6)` olduğu için indeks kullanılamıyor,
    sorgu canlıda 3,5 dakikada bile bitmiyordu. Artık önce küçük hesap planından
    kodlar bulunup fişlere kod ÖNEKİ ile gidiliyor.
    """

    def _yakala(self, plan_satirlari):
        class C(_SqlYakala):
            def sql_veri_oku(self, sql, **kw):
                self.sorgular.append(sql)
                if "MUHASEBE_HESAP_PLANI" in sql:
                    return {"Data": plan_satirlari}
                return {"Data": [{"hesap": "300.01.001", "borc": 1000.0}]}
        return C()

    def test_hesap_plani_once_sorgulanir(self) -> None:
        from infra.mikro_fetch import fetch_kredi_karti_borclari
        c = self._yakala([{"kod": "300.01", "ad": "KREDİ KARTLARI"}])
        fetch_kredi_karti_borclari(c, "2026-06-30")
        self.assertIn("MUHASEBE_HESAP_PLANI", c.sorgular[0])
        self.assertNotIn("JOIN", c.sorgular[1])          # fişlere join yok
        self.assertIn("fis_hesap_kod LIKE '300.01%'", c.sorgular[1])

    def test_kart_hesabi_yoksa_fislere_hic_gidilmez(self) -> None:
        """En pahalı sorgu hiç kurulmamalı — kurulumların çoğunda kart hesabı yok."""
        from infra.mikro_fetch import fetch_kredi_karti_borclari
        c = self._yakala([])
        self.assertEqual(fetch_kredi_karti_borclari(c, "2026-06-30"), [])
        self.assertEqual(len(c.sorgular), 1)

    def test_300_disi_hesap_alinmaz(self) -> None:
        from infra.mikro_fetch import fetch_kredi_karti_borclari
        c = self._yakala([{"kod": "320.55", "ad": "KREDİ KARTI SATICI"}])
        self.assertEqual(fetch_kredi_karti_borclari(c, "2026-06-30"), [])
        self.assertEqual(len(c.sorgular), 1)

    def test_alt_hesap_ana_hesabin_adini_alir(self) -> None:
        from infra.mikro_fetch import fetch_kredi_karti_borclari
        c = self._yakala([{"kod": "300.01", "ad": "KREDİ KARTLARI"}])
        rows = fetch_kredi_karti_borclari(c, "2026-06-30")
        self.assertEqual(rows[0]["hesap_ad"], "KREDİ KARTLARI")

    def test_like_jokerli_kod_elenir(self) -> None:
        """Kodda % olsa önek süzgeci tüm tabloyu çekerdi."""
        from infra.mikro_fetch import kredi_karti_hesaplari
        c = self._yakala([{"kod": "300.%1", "ad": "KREDİ KARTI"},
                          {"kod": "300.02", "ad": "KREDİ KARTI"}])
        self.assertEqual([k for k, _ in kredi_karti_hesaplari(c)], ["300.02"])


class TestMizanSorgusu(unittest.TestCase):
    """
    Mizan sorgusu — yıl sonu kapanışı ve tarama genişliği.

    Canlıda iki ayrı hata birleşiyordu: sorgunun alt tarih sınırı olmadığı için tüm
    tablo taranıyor (120 sn zaman aşımı), ve 31 Aralık seçilince o günün KAPANIŞ fişi
    hesaba girip bütün bakiyeleri sıfırlıyordu (aktif toplamı 176 bin TL). Kanıt:
    2025-12-31'de 514 satırlık 39,8 milyonluk kapanış fişi, 2025-01-01'de 571 satırlık
    36,1 milyonluk açılış fişi.
    """

    def _yakala(self, gun_fisleri):
        """gun_fisleri: {'YYYY-MM-DD': [fiş, …]} — gün sorgusu buradan cevaplanır."""
        class C(_SqlYakala):
            def sql_veri_oku(self, sql, **kw):
                self.sorgular.append(sql)
                if "fis_yevmiye_no AS yevmiye" in sql:
                    for gun, fisler in gun_fisleri.items():
                        if f">= '{gun}'" in sql:
                            return {"Data": fisler}
                    return {"Data": []}
                return {"Data": []}
        return C()

    @staticmethod
    def _fis(yevmiye, satir, ozkaynak=1):
        return {"yevmiye": yevmiye, "satir": satir, "borc": 1e6,
                "ozkaynak_var": ozkaynak, "gelir_var": 0}

    def test_acilis_fisi_varsa_aralik_yila_daralir(self) -> None:
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({"2025-01-01": [self._fis(1, 571)]})
        fetch_mizan(c, "2025-06-30")
        self.assertIn("fis_tarih >= '2025-01-01'", c.sorgular[-1])

    def test_acilis_fisi_yoksa_tum_gecmis_taranir(self) -> None:
        """Açılış fişi yokken daraltmak, o yıl öncesinin bakiyesini sessizce yok eder."""
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({})
        fetch_mizan(c, "2025-06-30")
        self.assertNotIn("fis_tarih >= '2025-01-01'", c.sorgular[-1])

    def test_kucuk_ozkaynak_fisi_acilis_sayilmaz(self) -> None:
        """Yıl başına düşen 2 satırlık düzeltme açılış fişi değildir."""
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({"2025-01-01": [self._fis(7, 2)]})
        fetch_mizan(c, "2025-06-30")
        self.assertNotIn("fis_tarih >= '2025-01-01'", c.sorgular[-1])

    def test_yil_sonunda_kapanis_fisi_dislanir(self) -> None:
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({"2025-12-31": [self._fis(20089, 514), self._fis(20085, 2)]})
        fetch_mizan(c, "2025-12-31")
        sql = c.sorgular[-1]
        self.assertIn("fis_yevmiye_no IN (20089, 20085)", sql)
        self.assertIn("NOT (fis_tarih >= '2025-12-31'", sql)

    def test_yil_ortasinda_kapanis_sorgusu_hic_yapilmaz(self) -> None:
        """31 Aralık değilse kapanış fişi aranmaz — boşuna tur atılmasın."""
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({})
        fetch_mizan(c, "2025-06-30")
        gun_sorgulari = [s for s in c.sorgular if "fis_yevmiye_no AS yevmiye" in s]
        self.assertEqual(len(gun_sorgulari), 1)      # yalnız açılış kontrolü

    def test_ozkaynaksiz_fis_kapanis_sayilmaz(self) -> None:
        from infra.mikro_fetch import fetch_mizan
        c = self._yakala({"2025-12-31": [self._fis(20078, 38, ozkaynak=0)]})
        fetch_mizan(c, "2025-12-31")
        self.assertNotIn("fis_yevmiye_no IN", c.sorgular[-1])

    def test_gun_sorgusu_patlarsa_mizan_yine_kurulur(self) -> None:
        """Yardımcı sorgu teşhis amaçlı; asıl mizanı düşürmemeli."""
        from infra.mikro_api import MikroAPIError
        from infra.mikro_fetch import fetch_mizan

        class C(_SqlYakala):
            def sql_veri_oku(self, sql, **kw):
                self.sorgular.append(sql)
                if "fis_yevmiye_no AS yevmiye" in sql:
                    raise MikroAPIError("gün sorgusu patladı")
                return {"Data": []}

        c = C()
        fetch_mizan(c, "2025-12-31")
        self.assertIn("GROUP BY fis_hesap_kod", c.sorgular[-1])


if __name__ == "__main__":
    unittest.main()


class TestTeshisHukumEsikleri(unittest.TestCase):
    """
    Hüküm eşikleri — canlı rakamlarla. İkisi de gerçek hataydı.

    (1) Satışta 5.494 faturadan 1'i çakışıyordu; «ortak > 0» eşiği «Yalnız Fatura'ya
        geç» diyordu. O ayar satışı 20,5 milyondan 1,1 milyona düşürürdü — teşhis
        aracının verebileceği en pahalı yanlış tavsiye.
    (2) Alışta girişlerin %100'ü depo transferiydi ve teşhis bunu kendi bastığı hâlde
        «açıklanamıyor» dedi: koşul sırası, dışarıdan gelen malın alış faturasına
        YAKIN olmasını arıyordu, sıfır olmasını değil.
    """

    @staticmethod
    def _cikti(fn, *a, **kw) -> str:
        import contextlib
        import io
        c = io.StringIO()
        with contextlib.redirect_stdout(c):
            fn(*a, **kw)
        return c.getvalue()

    def test_tek_cakisma_ayar_degistirtmez(self) -> None:
        from unittest.mock import patch

        import stok_diag_cli as sd
        with patch.object(sd, "donem_satirlari", return_value=[{
                "irsaliye_fatura": 5413, "fatura_fatura": 82, "birlesik_fatura": 5494}]):
            m = self._cikti(sd._fatura_ortakligi, None, "2026-01-01", "2026-07-28", 1.0)
        self.assertIn("AYRIK", m)
        self.assertIn("ihmal edilebilir", m)
        self.assertNotIn("Yalnız Fatura", m)

    def test_gercek_mukerrerlik_uyarir(self) -> None:
        from unittest.mock import patch

        import stok_diag_cli as sd
        # Faturaların yarısı hem irsaliye hem fatura satırı taşıyor → gerçek sorun.
        with patch.object(sd, "donem_satirlari", return_value=[{
                "irsaliye_fatura": 1000, "fatura_fatura": 1000, "birlesik_fatura": 1500}]):
            m = self._cikti(sd._fatura_ortakligi, None, "2026-01-01", "2026-07-28", 1.0)
        self.assertIn("Yalnız Fatura", m)

    def test_tamami_transfer_ise_alis_dogru_sayiliyor(self) -> None:
        from unittest.mock import patch

        import stok_diag_cli as sd
        kova = {(12, 0): [6592.0, 22_594_651.34], (3, 1): [2492.0, 14_665_701.10]}
        with patch.object(sd, "donem_satirlari", return_value=[
                {"transfer": 1, "tutar": 22_594_651.34, "adet": 6592}]):
            m = self._cikti(sd._alis_teshisi, None, "2026-01-01", "2026-07-28", kova)
        self.assertIn("TAMAMI depolar arası transfer", m)
        self.assertIn("DOĞRU", m)
        self.assertNotIn("açıklanmıyor", m)

    def test_disaridan_gelen_mal_varsa_transfer_hukmu_verilmez(self) -> None:
        from unittest.mock import patch

        import stok_diag_cli as sd
        kova = {(12, 0): [100.0, 20_000_000.0], (3, 1): [50.0, 14_000_000.0]}
        with patch.object(sd, "donem_satirlari", return_value=[
                {"transfer": 0, "tutar": 20_000_000.0, "adet": 100}]):
            m = self._cikti(sd._alis_teshisi, None, "2026-01-01", "2026-07-28", kova)
        self.assertNotIn("TAMAMI depolar arası transfer", m)
