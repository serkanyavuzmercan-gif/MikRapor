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

    def test_satis_ve_alis_ayri_yil_yil_doner(self) -> None:
        """Satışın maliyeti alışınkiyle karışmamalı; yıl kırılımı tutarlılığı gösterir."""
        from infra.mikro_fetch import fetch_stok_maliyet_teshis
        c = _SqlYakala()
        fetch_stok_maliyet_teshis(c, "2026-01-01", "2026-07-28")
        sql = c.sorgular[0]
        self.assertIn("sth_tip", sql.split("GROUP BY")[1])
        self.assertIn("SUM(sth_tutar) AS tutar", sql)
        self.assertIn(">= '2026-01-01'", sql)
        self.assertIn("< '2026-07-29'", sql)          # bitiş günü tam dahil


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
