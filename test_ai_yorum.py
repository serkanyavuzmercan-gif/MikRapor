"""Yapay Zekâ Yorumu — ayar/onay kapısı, veri paketi ve yorum ayrıştırma testleri."""

from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from domain.ai_yorum import (
    SISTEM_PROMPT,
    AiYorum,
    YilKapanis,
    ai_yorum_csv,
    ay_farki,
    build_ai_veri_paketi,
    yil_araligi,
    yillar_arasi_csv,
    yillar_tablosu,
)
from infra.ai_client import MAX_GIRDI_KARAKTER, AiHata, yorumla
from infra.ai_config import AiConfig
from infra.ai_saglayici import (
    SAGLAYICILAR,
    ModelListesiHatasi,
    ag_hata_mesaji,
    en_iyi_model,
    http_hata_mesaji,
    modelleri_getir,
    saglayici_bul,
)
from infra.mikro_fetch import _kur_makul


def _paket(bolumler=None):
    return build_ai_veri_paketi(
        yil=2026, bas="2026-01-01", bit="2026-12-31", firma="TEST A.Ş.",
        bolumler=bolumler if bolumler is not None else [("BİLANÇO", "Bölüm;Kalem;Tutar\nAKTİF;Nakit;1.000")],
    )


class TestAiConfig(unittest.TestCase):
    def test_hazir_icin_anahtar_ve_onay_yeter(self) -> None:
        """Model kullanıcıdan istenmez — çağrı anında otomatik seçilir."""
        self.assertTrue(AiConfig(api_key="sk-ant-x", onay=True).hazir)
        self.assertFalse(AiConfig().hazir)
        self.assertFalse(AiConfig(api_key="sk-ant-x").hazir)   # onay yok
        self.assertFalse(AiConfig(onay=True).hazir)             # anahtar yok

    def test_eksik_sebebi_anlasilir(self) -> None:
        self.assertIn("anahtar", AiConfig().eksik().lower())
        self.assertIn("onay", AiConfig(api_key="sk-x").eksik().lower())
        self.assertEqual(AiConfig(api_key="sk-x", onay=True).eksik(), "")

    def test_onay_geri_alinabilir(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        self.assertTrue(cfg.hazir)
        cfg.onay = False
        self.assertFalse(cfg.hazir)  # anahtar dursa da çağrı yapılamaz

    def test_anahtar_saglayici_basina_saklanir(self) -> None:
        """Claude'dan Gemini'ye geçince kullanıcı anahtarını yeniden girmesin."""
        cfg = AiConfig(saglayici="anthropic", api_key="sk-ant-1").normalized()
        cfg = AiConfig(saglayici="google", api_key="AIza-2",
                       anahtarlar=cfg.anahtarlar).normalized()
        self.assertEqual(cfg.anahtar_al("anthropic"), "sk-ant-1")
        self.assertEqual(cfg.anahtar_al("google"), "AIza-2")

    def test_ozel_saglayici_adres_ister(self) -> None:
        cfg = AiConfig(saglayici="ozel", api_key="k", onay=True)
        self.assertIn("adres", cfg.eksik().lower())
        cfg.ozel_base_url = "https://ornek.local/v1"
        self.assertTrue(cfg.normalized().hazir)
        self.assertEqual(cfg.normalized().etkin_base_url, "https://ornek.local/v1")


class TestSaglayicilar(unittest.TestCase):
    def test_beklenen_saglayicilar_var(self) -> None:
        kodlar = {s.kod for s in SAGLAYICILAR}
        for beklenen in ("anthropic", "openai", "google", "deepseek", "xai", "ozel"):
            self.assertIn(beklenen, kodlar)

    def test_groq_listede_yok(self) -> None:
        """Groq sürekli hata verdiği için çıkarıldı; «Özel» ile elle girilebilir."""
        self.assertNotIn("groq", {s.kod for s in SAGLAYICILAR})

    def test_bilinmeyen_kod_varsayilana_duser(self) -> None:
        """Kayıtlı ayarı «groq» kalmış kullanıcı da buraya düşer — çökmeden."""
        self.assertEqual(saglayici_bul("yok-boyle").kod, "anthropic")
        self.assertEqual(saglayici_bul("groq").kod, "anthropic")

    def test_anahtarsiz_model_listesi_agi_kullanmaz(self) -> None:
        with patch("infra.ai_saglayici._istek") as sahte:
            with self.assertRaises(ModelListesiHatasi):
                modelleri_getir(saglayici_bul("openai"), "")
            sahte.assert_not_called()

    def test_model_listesi_farkli_yanit_bicimlerini_okur(self) -> None:
        """OpenAI {'data':[{'id':…}]}, Google 'models/…' öneki, düz liste — hepsi."""
        for yanit, beklenen in (
            ({"data": [{"id": "gpt-x"}, {"id": "gpt-y"}]}, ["gpt-x", "gpt-y"]),
            ({"data": [{"name": "models/gemini-z"}]}, ["gemini-z"]),
            ({"models": ["a-model"]}, ["a-model"]),
        ):
            with patch("infra.ai_saglayici._istek", return_value=yanit):
                self.assertEqual(modelleri_getir(saglayici_bul("openai"), "k"), beklenen)

    def test_ozel_saglayici_adressiz_cagirmaz(self) -> None:
        with patch("infra.ai_saglayici._istek") as sahte:
            with self.assertRaises(ModelListesiHatasi):
                modelleri_getir(saglayici_bul("ozel"), "k")
            sahte.assert_not_called()


class TestOnaySizAgaCikilmaz(unittest.TestCase):
    """En kritik davranış: onay/anahtar yoksa HİÇBİR ağ çağrısı olmamalı."""

    def test_onay_yoksa_istemci_hic_kurulmaz(self) -> None:
        with patch("infra.ai_client._anthropic_cagir") as sahte, patch("infra.ai_client._openai_cagir") as sahte2:
            for cfg in (AiConfig(), AiConfig(api_key="sk-ant-x"), AiConfig(onay=True),
                        AiConfig(saglayici="ozel", api_key="k", onay=True)):  # adres yok
                with self.assertRaises(AiHata):
                    yorumla(cfg, _paket())
            sahte.assert_not_called()
            sahte2.assert_not_called()

    def test_bos_paket_gonderilmez(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        with patch("infra.ai_client._anthropic_cagir") as sahte, patch("infra.ai_client._openai_cagir") as sahte2:
            with self.assertRaises(AiHata):
                yorumla(cfg, _paket(bolumler=[]))
            sahte.assert_not_called()
            sahte2.assert_not_called()

    def test_asiri_buyuk_paket_sessizce_kirpilmaz(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        dev = _paket(bolumler=[("BÜYÜK", "x" * (MAX_GIRDI_KARAKTER + 10))])
        with patch("infra.ai_client._anthropic_cagir") as sahte, patch("infra.ai_client._openai_cagir") as sahte2:
            with self.assertRaises(AiHata) as ctx:
                yorumla(cfg, dev)
            self.assertIn("büyük", str(ctx.exception).lower())
            sahte.assert_not_called()
            sahte2.assert_not_called()


class TestOtomatikModelSecimi(unittest.TestCase):
    """Kullanıcı model yazmaz/seçmez — en günceli otomatik gelir."""

    def test_en_guncel_secilir(self) -> None:
        for kod, liste, beklenen in (
            ("anthropic", ["claude-haiku-4-5", "claude-opus-4-8", "claude-opus-5"], "claude-opus-5"),
            ("google", ["gemini-1.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"], "gemini-2.5-pro"),
            ("xai", ["grok-2", "grok-4"], "grok-4"),
        ):
            self.assertEqual(en_iyi_model(liste, saglayici_bul(kod)), beklenen)

    def test_kararli_surum_preview_i_yener(self) -> None:
        sec = en_iyi_model(["gemini-2.5-pro-preview", "gemini-2.5-pro"], saglayici_bul("google"))
        self.assertEqual(sec, "gemini-2.5-pro")

    def test_sohbet_disi_modeller_elenir(self) -> None:
        """Gömme/ses/görsel modelleri aday olmamalı."""
        liste = ["text-embedding-3-large", "whisper-large-v3", "dall-e-3", "gpt-5"]
        self.assertEqual(en_iyi_model(liste, saglayici_bul("openai")), "gpt-5")
        with patch("infra.ai_saglayici._istek", return_value={"data": [
                {"id": "text-embedding-3-large"}, {"id": "whisper-1"}, {"id": "gpt-5"}]}):
            self.assertEqual(modelleri_getir(saglayici_bul("openai"), "k"), ["gpt-5"])

    def test_google_generateContent_desteklemeyeni_atar(self) -> None:
        yanit = {"models": [
            {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        ]}
        with patch("infra.ai_saglayici._istek", return_value=yanit):
            self.assertEqual(modelleri_getir(saglayici_bul("google"), "k"), ["gemini-2.5-pro"])

    def test_liste_alinamazsa_onceki_modele_duser(self) -> None:
        from infra.ai_client import model_coz
        cfg = AiConfig(api_key="k", model="onceki-model", onay=True)
        with patch("infra.ai_client.guncel_model_sec", side_effect=ModelListesiHatasi("yok")):
            self.assertEqual(model_coz(cfg), "onceki-model")

    def test_liste_de_yedek_de_yoksa_acik_hata(self) -> None:
        from infra.ai_client import model_coz
        cfg = AiConfig(api_key="k", onay=True)
        with patch("infra.ai_client.guncel_model_sec", side_effect=ModelListesiHatasi("uç yok")):
            with self.assertRaises(AiHata) as ctx:
                model_coz(cfg)
        self.assertIn("uç yok", str(ctx.exception))


class TestHataMesajlari(unittest.TestCase):
    """«HTTP 400» hiçbir şey anlatmaz; kullanıcı ne yapacağını bilmeli."""

    def _hata(self, kod: int, mesaj: str = ""):
        govde = json.dumps({"error": {"message": mesaj}}).encode()
        return urllib.error.HTTPError("https://x/y", kod, "err", {}, io.BytesIO(govde))

    def test_kodlar_turkce_aciklanir(self) -> None:
        for kod, aranan in ((400, "model adı"), (401, "anahtar"), (403, "yetkisiz"),
                            (404, "bulunamadı"), (429, "kota"), (503, "geçici")):
            self.assertIn(aranan, http_hata_mesaji(self._hata(kod)).lower())

    def test_saglayicinin_aciklamasi_eklenir(self) -> None:
        m = http_hata_mesaji(self._hata(400, "models/GEMINI is not found"), model="GEMINI")
        self.assertIn("GEMINI", m)
        self.assertIn("models/GEMINI is not found", m)

    def test_turkce_kucuk_harf_eslesmesi(self) -> None:
        """'İyi'.lower() birleşik nokta üretir; bölüm rengi bu yüzden yanlış çıkıyordu."""
        from domain.ortak import tr_kucuk
        from ui.ai_yorum_view import _bolum_rengi
        self.assertIn("iyi giden", tr_kucuk("İyi Giden 3 Şey"))
        self.assertEqual(tr_kucuk("IŞIK"), "ışık")
        # Her başlık kendi rengini almalı; hepsi aynı (varsayılan) olmamalı.
        renkler = {_bolum_rengi(b) for b in (
            "Özet", "İyi Giden 3 Şey", "Dikkat Edilmesi Gereken 3 Şey", "Karar Gerektiren 3 Konu")}
        self.assertEqual(len(renkler), 4)

    def test_zaman_asimi_ve_baglanti(self) -> None:
        self.assertIn("zaman aşımı", ag_hata_mesaji(TimeoutError()).lower())
        self.assertIn("adres çözümlenemedi", ag_hata_mesaji(
            urllib.error.URLError("Name or service not known")).lower())
        self.assertIn("ssl", ag_hata_mesaji(
            urllib.error.URLError("certificate verify failed")).lower())


class TestOpenAiUyumluYol(unittest.TestCase):
    """Gemini/DeepSeek/xAI tek şemadan geçer — istek gövdesi doğru kurulmalı."""

    def _sahte_yanit(self, yakalanan):
        class _Yanit(io.BytesIO):
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False

        def _urlopen(istek, **kw):
            yakalanan["url"] = istek.full_url
            yakalanan["auth"] = dict(istek.headers).get("Authorization")
            yakalanan["body"] = json.loads(istek.data.decode())
            return _Yanit(json.dumps({
                "choices": [{"message": {"content": "## Özet\nTamam."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }).encode())
        return _urlopen

    def test_istek_dogru_kurulur(self) -> None:
        yakalanan: dict = {}
        cfg = AiConfig(saglayici="deepseek", api_key="sk_test", onay=True)
        with patch("urllib.request.urlopen", self._sahte_yanit(yakalanan)), \
                patch("infra.ai_client.guncel_model_sec", return_value="bir-model"):
            y = yorumla(cfg, _paket())
        self.assertEqual(yakalanan["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(yakalanan["auth"], "Bearer sk_test")
        self.assertEqual(yakalanan["body"]["model"], "bir-model")
        self.assertEqual([m["role"] for m in yakalanan["body"]["messages"]], ["system", "user"])
        self.assertIn("AKTİF;Nakit;1.000", yakalanan["body"]["messages"][1]["content"])
        self.assertIn("Tamam.", y.metin)
        self.assertEqual((y.girdi_token, y.cikti_token), (12, 3))

    def test_ozel_saglayici_kendi_adresine_gider(self) -> None:
        yakalanan: dict = {}
        cfg = AiConfig(saglayici="ozel", api_key="k", onay=True,
                       ozel_base_url="https://kendi-sunucum.local/v1")
        with patch("urllib.request.urlopen", self._sahte_yanit(yakalanan)), \
                patch("infra.ai_client.guncel_model_sec", return_value="m"):
            yorumla(cfg, _paket())
        self.assertEqual(yakalanan["url"], "https://kendi-sunucum.local/v1/chat/completions")

    def test_https_disi_adres_reddedilir(self) -> None:
        cfg = AiConfig(saglayici="ozel", api_key="k", model="m", onay=True,
                       ozel_base_url="http://sifresiz.local/v1")
        with patch("urllib.request.urlopen") as sahte, \
                patch("infra.ai_client.guncel_model_sec", return_value="m"):
            with self.assertRaises(AiHata):
                yorumla(cfg, _paket())
            sahte.assert_not_called()


class TestDonemBaglami(unittest.TestCase):
    """Yıl ortasında çalıştırılınca model yılı bitmiş sanmamalı (canlıda öyle sanmıştı)."""

    def _yariyil(self):
        return build_ai_veri_paketi(
            yil=2026, bas="2026-01-01", bit="2026-07-27", bolumler=[("A", "veri")],
            bugun="2026-07-27", tamamlandi=False, ay_sayisi=7)

    def test_devam_eden_yil_acikca_soylenir(self) -> None:
        n = self._yariyil().donem_notu
        self.assertIn("HENÜZ BİTMEDİ", n)
        self.assertIn("ilk 7 ayını", n)
        self.assertIn("2026-07-27", n)          # bugünün tarihi modele verilir
        self.assertIn("KULLANMA", n)            # «yılı kapattı» yasağı

    def test_kapanis_uyarisi_verilir(self) -> None:
        """Yıl sonu kapanışı yapılmadan resmî kâr şişik görünür — model uyarılmalı."""
        n = self._yariyil().donem_notu
        self.assertIn("KAPANIŞI HENÜZ YAPILMADI", n)
        self.assertIn("62x", n)
        self.assertIn("YÜKSEK", n)
        self.assertIn("NAKİT VE KÂRLILIK", n)   # fiili marja yönlendirme

    def test_biten_yilda_uyari_yok(self) -> None:
        n = build_ai_veri_paketi(
            yil=2025, bas="2025-01-01", bit="2025-12-31", bolumler=[("A", "veri")],
            bugun="2026-07-27", tamamlandi=True, ay_sayisi=12).donem_notu
        self.assertIn("TAMAMLANDI", n)
        self.assertNotIn("HENÜZ BİTMEDİ", n)
        self.assertNotIn("KAPANIŞI HENÜZ YAPILMADI", n)

    def test_baglam_gonderilen_metne_girer(self) -> None:
        m = self._yariyil().metin
        self.assertIn("BUGÜNÜN TARİHİ", m)
        self.assertIn("DÖNEM DURUMU", m)

    def test_prompt_donem_durumuna_uymayi_emreder(self) -> None:
        self.assertIn("DÖNEM DURUMU", SISTEM_PROMPT)


class TestYilAraligi(unittest.TestCase):
    """Aralık kaç yıl kapsıyor ve sınırı aşınca ne düşüyor."""

    def test_tek_yil(self) -> None:
        self.assertEqual(yil_araligi("2026-01-01", "2026-07-27"), ([2026], 0))

    def test_bes_yil_tam_sinirda_kirpilmaz(self) -> None:
        yillar, dusen = yil_araligi("2021-01-01", "2025-12-31")
        self.assertEqual(yillar, [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(dusen, 0)

    def test_sinir_asilinca_en_yeni_yillar_kalir(self) -> None:
        """Eski yıl değil, YENİ yıl önemlidir — kırpma baştan yapılmalı."""
        yillar, dusen = yil_araligi("2016-01-01", "2026-07-27")
        self.assertEqual(yillar, [2022, 2023, 2024, 2025, 2026])
        self.assertEqual(dusen, 6)

    def test_ters_aralik_duzeltilir(self) -> None:
        self.assertEqual(yil_araligi("2026-01-01", "2024-01-01")[0], [2024, 2025, 2026])

    def test_bos_tarih_bos_liste(self) -> None:
        self.assertEqual(yil_araligi("", ""), ([], 0))


class TestYillarArasi(unittest.TestCase):
    """Yıllar arası karşılaştırma tablosu ve çok yıllı kapsam notu."""

    @staticmethod
    def _kapanislar() -> list[YilKapanis]:
        return [
            YilKapanis(yil=2024, net_satis=1_000_000.0, brut_kar=250_000.0,
                       net_kar=100_000.0, stok=3_000_000.0),
            YilKapanis(yil=2025, net_satis=2_000_000.0, brut_kar=300_000.0,
                       net_kar=50_000.0, stok=5_000_000.0),
        ]

    def test_yillar_sutun_olur(self) -> None:
        csv = yillar_arasi_csv(self._kapanislar())
        self.assertTrue(csv.startswith("Kalem;2024;2025"))
        self.assertIn("Net Satışlar;1000000,00;2000000,00", csv)
        self.assertIn("Brüt Marj (%);25,00;15,00", csv)

    def test_yillar_sirasiz_verilse_de_kronolojik_dizilir(self) -> None:
        csv = yillar_arasi_csv(list(reversed(self._kapanislar())))
        self.assertTrue(csv.startswith("Kalem;2024;2025"))

    def test_tek_yil_tablo_uretmez(self) -> None:
        """Tek yılda karşılaştırma yok — boş bölüm modele gitmemeli."""
        self.assertEqual(yillar_arasi_csv(self._kapanislar()[:1]), "")

    def test_kiyasi_bozan_yillar_isaretlenir(self) -> None:
        k = self._kapanislar()
        k[1].tam = False
        k[0].maliyet_eksik = True
        csv = yillar_arasi_csv(k)
        self.assertIn("2025 yılı TAMAMLANMADI", csv)
        self.assertIn("2024 yılında satışların maliyeti", csv)

    def _cok_yilli(self):
        return build_ai_veri_paketi(
            yil=2026, bas="2026-01-01", bit="2026-07-27", bolumler=[("A", "veri")],
            bugun="2026-07-27", tamamlandi=False, ay_sayisi=7,
            yillar=[2026, 2024, 2025])   # sırasız gelse de düzelmeli

    def test_kapsam_notu_odak_yili_ayirir(self) -> None:
        """Model geçmiş yıllar için ham kırılım olduğunu sanmamalı."""
        n = self._cok_yilli().kapsam_notu
        self.assertIn("2024–2026", n)
        self.assertIn("YALNIZ 2026 yılına aittir", n)
        self.assertIn("NOMİNAL TL", n)

    def test_aralik_en_eski_yildan_baslar(self) -> None:
        p = self._cok_yilli()
        self.assertEqual(p.aralik_bas, "2024-01-01")
        self.assertIn("VERİ ARALIĞI: 2024-01-01 – 2026-07-27", p.metin)

    def test_tek_yilda_kapsam_notu_yok(self) -> None:
        p = build_ai_veri_paketi(
            yil=2026, bas="2026-01-01", bit="2026-07-27", bolumler=[("A", "veri")],
            yillar=[2026])
        self.assertEqual(p.kapsam_notu, "")
        self.assertEqual(p.aralik_bas, "2026-01-01")
        self.assertNotIn("ÇOK YILLI", p.metin)

    def test_yorum_kapsami_bas_bitten_genis_olabilir(self) -> None:
        y = AiYorum(yil=2026, bas="2026-01-01", bit="2026-07-27", kapsam_bas="2024-01-01")
        self.assertEqual(y.aralik, "2024-01-01 – 2026-07-27")
        self.assertIn("DÖNEM;2024-01-01 – 2026-07-27", ai_yorum_csv(y))

    def test_kapsam_bos_ise_bas_kullanilir(self) -> None:
        y = AiYorum(yil=2026, bas="2026-01-01", bit="2026-07-27")
        self.assertEqual(y.aralik, "2026-01-01 – 2026-07-27")

    def test_prompt_cok_yilli_gidisati_ister(self) -> None:
        self.assertIn("YILLAR ARASI KARŞILAŞTIRMA", SISTEM_PROMPT)


class TestOranTablosu(unittest.TestCase):
    """Yıllar arası asıl tahlil oranlarda: stok, kredi borçluluğu, kârlılık."""

    @staticmethod
    def _yil(yil: int, **ek) -> YilKapanis:
        temel = dict(
            net_satis=10_000_000.0, brut_kar=2_000_000.0, faaliyet_kari=1_000_000.0,
            net_kar=500_000.0, smm=-8_000_000.0, stok=2_000_000.0, alacak=2_500_000.0,
            donen=7_000_000.0, kvyk=5_000_000.0, uvyk=1_000_000.0, ozkaynak=4_000_000.0,
            aktif_toplam=12_500_000.0, banka_kredisi=2_500_000.0,
            finansman_gideri=-300_000.0)
        temel.update(ek)
        return YilKapanis(yil=yil, **temel)

    def _csv(self, **ek) -> str:
        return yillar_arasi_csv([self._yil(2024), self._yil(2025, **ek)])

    def test_stok_oranlari(self) -> None:
        """Kullanıcının en önemli dediği kalem: stok gerçekten dönüyor mu."""
        csv = self._csv()
        self.assertIn("Stok Devir Hızı (kez/yıl);4,00;4,00", csv)
        self.assertIn("Stok Bekleme Süresi (gün);91,25;91,25", csv)
        self.assertIn("Stok / Net Satış (%);20,00;20,00", csv)

    def test_kredi_borclulugu(self) -> None:
        csv = self._csv()
        self.assertIn("Banka Kredisi (dönem sonu);2500000,00;2500000,00", csv)
        self.assertIn("Banka Kredisi / Aktif (%);20,00;20,00", csv)
        self.assertIn("Finansman Gideri / Net Satış (%);3,00;3,00", csv)
        self.assertIn("Borç / Özkaynak (x);1,50;1,50", csv)

    def test_karlilik_oranlari(self) -> None:
        csv = self._csv()
        self.assertIn("Faaliyet Marjı (%);10,00;10,00", csv)
        self.assertIn("Özkaynak Kârlılığı — ROE (%);12,50;12,50", csv)
        self.assertIn("Aktif Kârlılığı — ROA (%);4,00;4,00", csv)

    def test_likidite_ve_tahsilat(self) -> None:
        csv = self._csv()
        self.assertIn("Cari Oran (x);1,40;1,40", csv)
        self.assertIn("Asit-Test (x);1,00;1,00", csv)
        self.assertIn("Alacak Tahsil Süresi — DSO (gün);91,25;91,25", csv)

    def test_maliyet_yoksa_stok_devri_uydurulmaz(self) -> None:
        """SMM girilmemişse devir hızı hesaplanamaz — 0,00 yazmak yanlış olur."""
        csv = self._csv(smm=0.0, maliyet_eksik=True)
        self.assertIn("Stok Devir Hızı (kez/yıl);4,00;\r\n", csv + "\r\n")
        self.assertIn("Stok / Net Satış (%);20,00;20,00", csv)   # bu yine hesaplanır

    def test_negatif_ozkaynakta_oran_bos_kalir(self) -> None:
        """Özkaynak eksiyken ROE/borç-özkaynak matematiksel olarak anlamsız."""
        k = self._yil(2025, ozkaynak=-8_484.0)
        self.assertIsNone(k.roe)
        self.assertIsNone(k.borc_ozkaynak)
        self.assertIsNotNone(k.roa)      # bu hâlâ anlamlı

    def test_satis_yoksa_marj_bos(self) -> None:
        k = YilKapanis(yil=2025, net_satis=0.0, brut_kar=100.0)
        self.assertIsNone(k.brut_marj)
        self.assertIsNone(k.dso)

    def test_prompt_stok_kredi_karlilik_ister(self) -> None:
        self.assertIn("ORANLAR VE DEVİR HIZLARI", SISTEM_PROMPT)
        for anahtar in ("STOK", "KREDİ BORÇLULUĞU", "KÂRLILIK"):
            self.assertIn(anahtar, SISTEM_PROMPT)


class TestMukayeseTablosu(unittest.TestCase):
    """Yıllar arası mukayese DETERMİNİSTİK olmalı — modele bırakılırsa satır seçiyor."""

    @staticmethod
    def _yillar() -> list[YilKapanis]:
        def mk(yil, satis, usd, kur):
            return YilKapanis(
                yil=yil, net_satis=satis, brut_kar=satis * 0.12, net_kar=satis * 0.02,
                smm=-satis * 0.88, stok=140_000.0, alacak=satis * 0.28, donen=satis * 0.38,
                kvyk=satis * 0.4, uvyk=satis * 0.05, ozkaynak=satis * 0.15,
                aktif_toplam=satis * 0.8, banka_kredisi=satis * 0.06,
                finansman_gideri=-satis * 0.02, satis_usd=usd, kur_son=kur)
        return [mk(2021, 20_000_000.0, 1_500_430.0, 13.3),
                mk(2023, 31_000_000.0, 1_184_243.0, 27.0),
                mk(2025, 41_200_000.0, 1_050_163.0, 42.59)]

    def _bul(self, baslik: str, etiket: str):
        _, bolumler = yillar_tablosu(self._yillar())
        bolum = next(b for b in bolumler if b.baslik == baslik)
        return next(s for s in bolum.satirlar if s.etiket == etiket)

    def test_tum_yillar_sutun_olur(self) -> None:
        yillar, bolumler = yillar_tablosu(self._yillar())
        self.assertEqual(yillar, [2021, 2023, 2025])
        for bolum in bolumler:
            for satir in bolum.satirlar:
                self.assertEqual(len(satir.hucreler), 3, satir.etiket)

    def test_uc_bolum_de_kurulur(self) -> None:
        _, bolumler = yillar_tablosu(self._yillar())
        self.assertEqual([b.baslik for b in bolumler], [
            "TUTARLAR (TL)",
            "DOLAR BAZINDA",
            "ORANLAR VE DEVİR HIZLARI"])

    def test_dolar_bazinda_satis_dususu_gorunur(self) -> None:
        """Kullanıcının asıl istediği: TL'de büyürken dolarda küçülme."""
        tl = self._bul("TUTARLAR (TL)", "Net Satışlar")
        usd = self._bul("DOLAR BAZINDA", "Net Satışlar")
        self.assertEqual(tl.hucreler, ["20,0 milyon", "31,0 milyon", "41,2 milyon"])
        self.assertEqual(tl.degisim, "%+106")
        self.assertTrue(tl.iyi)
        self.assertEqual(usd.degisim, "%-30")
        self.assertFalse(usd.iyi)          # dolarda küçülme kötü, kırmızı

    def test_tutar_yuzde_oran_puan_degisir(self) -> None:
        """Tutarda yüzde, oranda puan — «cari oran %-33 düştü» yanıltıcı olurdu."""
        self.assertIn("puan", self._bul("ORANLAR VE DEVİR HIZLARI", "Brüt Marj (%)").degisim)
        self.assertNotIn("puan", self._bul("TUTARLAR (TL)", "Stok").degisim)
        self.assertNotIn("%", self._bul("ORANLAR VE DEVİR HIZLARI", "Cari Oran").degisim)

    def test_borc_artisi_kotu_alacak_azalisi_iyi(self) -> None:
        """Yön anlamı kaleme göre değişir: satış artışı iyi, borç artışı kötü."""
        self.assertFalse(self._bul("TUTARLAR (TL)", "Kısa Vadeli Borç").iyi)
        self.assertFalse(self._bul("TUTARLAR (TL)", "Ticari Alacak").iyi)
        self.assertTrue(self._bul("TUTARLAR (TL)", "Özkaynak").iyi)

    def test_hesaplanamayan_hucre_tire_olur(self) -> None:
        k = self._yillar()
        k[2].maliyet_eksik = True
        k[2].smm = 0.0
        _, bolumler = yillar_tablosu(k)
        satir = next(s for b in bolumler for s in b.satirlar
                     if s.etiket == "Stok Devir Hızı (kez/yıl)")
        self.assertEqual(satir.hucreler[-1], "—")
        self.assertEqual(satir.degisim, "—")    # uç hesaplanamıyorsa değişim de yok

    def test_kur_yoksa_dolar_bolumu_hic_gelmez(self) -> None:
        k = self._yillar()
        k[1].kur_son = 0.0
        _, bolumler = yillar_tablosu(k)
        self.assertNotIn("DOLAR BAZINDA",
                         [b.baslik for b in bolumler])
        self.assertIn("TUTARLAR (TL)", [b.baslik for b in bolumler])

    def test_birim_acik_yazilir(self) -> None:
        """«B» Türkçede milyar diye okunuyordu; 650 bin ile 650 milyar karışıyordu."""
        k = self._yillar()
        k[0].net_satis, k[2].net_satis = 650_000.0, 2_400_000_000.0
        _, bolumler = yillar_tablosu(k)
        satir = next(s for b in bolumler for s in b.satirlar if s.etiket == "Net Satışlar")
        self.assertEqual(satir.hucreler[0], "650 bin")
        self.assertEqual(satir.hucreler[-1], "2,4 milyar")
        self.assertNotIn("M", "".join(satir.hucreler))

    def test_milyar_esigi(self) -> None:
        from domain.ai_yorum import _kisa
        self.assertEqual(_kisa(2_400_000_000.0), "2,4 milyar")
        self.assertEqual(_kisa(41_200_000.0), "41,2 milyon")
        self.assertEqual(_kisa(650_000.0), "650 bin")
        self.assertEqual(_kisa(42.61), "43")

    def test_negatif_hucreler_isaretlenir(self) -> None:
        """Kırmızıya boyanacak hücreleri görünüm değil domain belirler."""
        satir = self._bul("TUTARLAR (TL)", "Özkaynak")
        self.assertEqual(satir.eksi, [False, False, False])
        k = self._yillar()
        k[2].ozkaynak = -8_484.0
        _, bolumler = yillar_tablosu(k)
        ozk = next(s for b in bolumler for s in b.satirlar if s.etiket == "Özkaynak")
        self.assertEqual(ozk.eksi[-1], True)

    def test_yillar_boyu_sabit_satir_isaretlenir(self) -> None:
        """Bilanço hesapları işlenmiyorsa mizan her yıl aynı çıkar — bu veri şüphesidir."""
        k = self._yillar()
        for y in k:
            y.stok = 139_999.18          # canlıda beş yıl boyunca kuruşu kuruşuna aynıydı
        _, bolumler = yillar_tablosu(k)
        stok = next(s for b in bolumler for s in b.satirlar if s.etiket == "Stok")
        self.assertTrue(stok.sabit)
        satis = next(s for b in bolumler for s in b.satirlar if s.etiket == "Net Satışlar")
        self.assertFalse(satis.sabit)     # gerçekten değişen satır işaretlenmemeli

    def test_sifir_satiri_sabit_sayilmaz(self) -> None:
        """Hepsi sıfır olan kalem «şüpheli» değil, sadece boş."""
        k = self._yillar()
        for y in k:
            y.uvyk = 0.0
        _, bolumler = yillar_tablosu(k)
        uv = next(s for b in bolumler for s in b.satirlar if s.etiket == "Uzun Vadeli Borç")
        self.assertFalse(uv.sabit)

    def test_tek_yilda_tablo_yok(self) -> None:
        self.assertEqual(yillar_tablosu(self._yillar()[:1]), ([], []))

    def test_veritabaninda_olmayan_yil_dolu_degil(self) -> None:
        """Boş yılın sorgusu hata değil sıfır döner; tabloya girerse trend uydurulur."""
        self.assertFalse(YilKapanis(yil=2019).dolu)
        self.assertFalse(YilKapanis(yil=2019, stok=140_000.0).dolu)   # yalnız devir kalıntısı
        self.assertTrue(YilKapanis(yil=2025, net_satis=1.0).dolu)
        self.assertTrue(YilKapanis(yil=2025, aktif_toplam=1.0).dolu)

    def test_csv_mukayeseyi_icerir(self) -> None:
        """Excel'de kendi grafiğini çizebilsin diye CSV'ye de girer."""
        csv = ai_yorum_csv(AiYorum(yil=2025, bas="2025-01-01", bit="2025-12-31",
                                   kapsam_bas="2021-01-01", kapanislar=self._yillar()))
        self.assertIn("MUKAYESE;Kalem;2021;2023;2025;2021→2025", csv)
        self.assertIn("MUKAYESE;Net Satışlar;20,0 milyon;31,0 milyon;41,2 milyon;%+106", csv)

    def test_kapanissiz_yorumda_csv_bozulmaz(self) -> None:
        csv = ai_yorum_csv(AiYorum(yil=2025, bas="2025-01-01", bit="2025-12-31"))
        self.assertNotIn("MUKAYESE", csv)


class TestKararBolumu(unittest.TestCase):
    """«Bu Ay Yapılacak 3 İş» yemek tarifi gibiydi — bu bir rapor."""

    def test_yapilacaklar_basligi_kaldirildi(self) -> None:
        self.assertNotIn("Bu Ay Yapılacak", SISTEM_PROMPT)
        self.assertIn("## Karar Gerektiren 3 Konu", SISTEM_PROMPT)

    def test_emir_ve_zaman_bicme_yasak(self) -> None:
        self.assertIn("yapılacaklar listesi DEĞİLDİR", SISTEM_PROMPT)
        self.assertIn("zaman biçme", SISTEM_PROMPT)


class TestDovizBazli(unittest.TestCase):
    """Yüksek enflasyonda düz TL kıyası yanıltır — dolar karşılığı verilmeli."""

    @staticmethod
    def _kapanislar(kur_2023: float = 27.0, kur_2025: float = 42.3) -> list[YilKapanis]:
        return [
            YilKapanis(yil=2023, net_satis=27_000_000.0, stok=8_000_000.0,
                       alacak=6_000_000.0, satis_usd=1_000_000.0, kur_son=kur_2023),
            YilKapanis(yil=2025, net_satis=41_200_000.0, stok=12_000_000.0,
                       alacak=11_360_000.0, satis_usd=800_000.0, kur_son=kur_2025),
        ]

    def test_doviz_blogu_yazilir(self) -> None:
        csv = yillar_arasi_csv(self._kapanislar())
        self.assertIn("DÖVİZ BAZLI", csv)
        self.assertIn("TL/USD kuru (dönem sonu);27,00;42,30", csv)
        self.assertIn("Net Satışlar (USD);1000000,00;800000,00", csv)

    def test_stok_ve_alacak_dolara_cevrilir(self) -> None:
        """Kullanıcının işaret ettiği yer: stok/alacakta nominal TL en çok yanıltır."""
        csv = yillar_arasi_csv(self._kapanislar())
        self.assertIn("Stok (USD);296296,30;283687,94", csv)      # TL'de arttı, USD'de düştü
        self.assertIn("Ticari Alacak (USD);222222,22;268557,92", csv)

    def test_kur_yoksa_blok_hic_yazilmaz(self) -> None:
        """Güvenilir kur olmadan uydurma dolar rakamı vermektense hiç verme."""
        k = self._kapanislar()
        k[1].kur_son = 0.0
        csv = yillar_arasi_csv(k)
        self.assertNotIn("DÖVİZ BAZLI", csv)
        self.assertIn("Net Satışlar;", csv)      # TL tablosu yine de durur

    def test_usd_kursuz_sifir_doner(self) -> None:
        self.assertEqual(YilKapanis(yil=2025).usd(1_000.0), 0.0)

    def test_prompt_enflasyon_ve_doviz_kurallari(self) -> None:
        self.assertIn("ENFLASYON YÜKSEKTİR", SISTEM_PROMPT)
        self.assertIn("DÖVİZ BAZLI", SISTEM_PROMPT)
        self.assertIn("kendi bilgimdeki TÜFE", SISTEM_PROMPT)


class TestKurMakul(unittest.TestCase):
    """İma edilen kur — meblag1 boş/anlamsızsa 0 dönmeli (uydurma kur yok)."""

    def test_makul_kur_hesaplanir(self) -> None:
        self.assertAlmostEqual(_kur_makul(42_300_000.0, 1_000_000.0), 42.3)

    def test_doviz_bos_ise_sifir(self) -> None:
        self.assertEqual(_kur_makul(42_300_000.0, 0.0), 0.0)

    def test_band_disi_kur_reddedilir(self) -> None:
        self.assertEqual(_kur_makul(1_000.0, 1_000_000.0), 0.0)   # 0,001 — çok düşük
        self.assertEqual(_kur_makul(1_000_000.0, 100.0), 0.0)     # 10.000 — çok yüksek

    def test_isaret_onemsiz(self) -> None:
        self.assertAlmostEqual(_kur_makul(-42_300_000.0, -1_000_000.0), 42.3)


class TestVeriBayatligi(unittest.TestCase):
    """Geçmiş yıl seçilince model 'bugün' sanıyordu — bugüne çekilmeli."""

    @staticmethod
    def _bayat(gecikme: int = 7):
        return build_ai_veri_paketi(
            yil=2025, bas="2025-01-01", bit="2025-12-31", bolumler=[("A", "veri")],
            bugun="2026-07-27", tamamlandi=True, ay_sayisi=12, gecikme_ay=gecikme,
            calisma_yili=2025)

    def test_ay_farki(self) -> None:
        self.assertEqual(ay_farki("2025-12-31", "2026-07-27"), 6)
        self.assertEqual(ay_farki("2025-12-31", "2026-08-01"), 7)
        self.assertEqual(ay_farki("2026-07-01", "2026-07-27"), 0)
        self.assertEqual(ay_farki("2026-12-31", "2026-07-27"), 0)   # gelecek → 0
        self.assertEqual(ay_farki("bozuk", "2026-07-27"), 0)

    def test_bayat_veri_uyarisi(self) -> None:
        n = self._bayat().donem_notu
        self.assertIn("VERİ GÜNCEL DEĞİL", n)
        self.assertIn("2026-07-27", n)          # bugün
        self.assertIn("2025-12-31", n)          # verinin sonu
        self.assertIn("7 ay", n)

    def test_yanlis_zaman_kipi_yasaklanir(self) -> None:
        n = self._bayat().donem_notu
        self.assertIn("«şu an»", n)
        self.assertIn("2025-12-31 itibarıyla", n)

    def test_bosluk_kayit_eksikligi_sanilmaz(self) -> None:
        """Model «kayıtlarınız eksik, acilen işleyin» diyordu — 2026 başka DB'de."""
        n = self._bayat().donem_notu
        self.assertIn("KAYIT EKSİKLİĞİ DEĞİLDİR", n)
        self.assertIn("2025 ÇALIŞMA YILI veritabanından", n)
        self.assertIn("Veride Göremediklerim", n)   # öneri değil, eksik notu

    def test_calisma_yili_bilinmiyorsa_da_uyari_calisir(self) -> None:
        n = build_ai_veri_paketi(
            yil=2025, bas="2025-01-01", bit="2025-12-31", bolumler=[("A", "veri")],
            bugun="2026-07-27", tamamlandi=True, ay_sayisi=12, gecikme_ay=6).donem_notu
        self.assertIn("KAYIT EKSİKLİĞİ DEĞİLDİR", n)
        self.assertNotIn("0 ÇALIŞMA YILI", n)

    def test_guncel_veride_uyari_yok(self) -> None:
        self.assertNotIn("VERİ GÜNCEL DEĞİL", self._bayat(gecikme=1).donem_notu)


class TestVeriPaketi(unittest.TestCase):
    def test_bos_bolumler_elenir(self) -> None:
        p = build_ai_veri_paketi(
            yil=2026, bas="2026-01-01", bit="2026-12-31",
            bolumler=[("A", "veri"), ("B", ""), ("C", "   ")])
        self.assertEqual([b for b, _ in p.bolumler], ["A"])

    def test_metin_firma_donem_ve_bolumleri_icerir(self) -> None:
        m = _paket().metin
        self.assertIn("TEST A.Ş.", m)
        self.assertIn("2026-01-01", m)
        self.assertIn("### BİLANÇO", m)
        self.assertIn("AKTİF;Nakit;1.000", m)

    def test_ozet_satiri_ne_gonderildigini_soyler(self) -> None:
        ozet = _paket().ozet_satiri()
        self.assertIn("1 bölüm", ozet)
        self.assertIn("BİLANÇO", ozet)

    def test_sistem_prompt_uydurmayi_yasaklar(self) -> None:
        self.assertIn("uydurma", SISTEM_PROMPT.lower())
        for baslik in ("## Özet", "## İyi Giden 3 Şey", "## Dikkat Edilmesi Gereken 3 Şey",
                       "## Karar Gerektiren 3 Konu", "## Veride Göremediklerim"):
            self.assertIn(baslik, SISTEM_PROMPT)


class TestYorumAyristirma(unittest.TestCase):
    def test_bolumlere_ayirma(self) -> None:
        from ui.ai_yorum_view import bolumlere_ayir
        bolumler = bolumlere_ayir(
            "## Özet\nİyi gidiyor.\n\n## Dikkat\n- Alacaklar yaşlanıyor\n- Kredi yükü var\n")
        self.assertEqual([b for b, _ in bolumler], ["Özet", "Dikkat"])
        self.assertEqual(len(bolumler[1][1]), 2)

    def test_baslik_yoksa_metin_kaybolmaz(self) -> None:
        from ui.ai_yorum_view import bolumlere_ayir
        bolumler = bolumlere_ayir("Model başlık kullanmadı ama yine de bir şey yazdı.")
        self.assertEqual(len(bolumler), 1)
        self.assertIn("yine de", bolumler[0][1][0])

    def test_turkce_buyuk_harf(self) -> None:
        """Başlıklar büyütülürken 'i' → 'İ' olmalı (DIKKAT değil DİKKAT)."""
        from domain.ortak import tr_buyuk
        self.assertEqual(tr_buyuk("Dikkat Edilmesi Gereken 3 Şey"), "DİKKAT EDİLMESİ GEREKEN 3 ŞEY")
        self.assertEqual(tr_buyuk("Bu Ay Yapılacak 3 İş"), "BU AY YAPILACAK 3 İŞ")
        self.assertEqual(tr_buyuk("Özet"), "ÖZET")

    def test_csv_yorumu_tasir(self) -> None:
        y = AiYorum(metin="## Özet\nİyi gidiyor.", model="claude-opus-5",
                    bas="2026-01-01", bit="2026-12-31", girdi_token=10, cikti_token=20)
        csv = ai_yorum_csv(y)
        self.assertIn("MODEL;claude-opus-5", csv)
        self.assertIn("İyi gidiyor.", csv)
        self.assertEqual(y.toplam_token, 30)


if __name__ == "__main__":
    unittest.main()
