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
    degisim_basligi,
    kiyas_tabani,
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
    """Modele giden CSV — ekranla aynı satırlardan, ham rakamlarla."""

    @staticmethod
    def _kapanislar() -> list[YilKapanis]:
        return [
            YilKapanis(yil=2024, net_satis=1_000_000.0, brut_kar=250_000.0,
                       net_kar=100_000.0, stok=3_000_000.0, smm=-750_000.0,
                       satis_usd=30_000.0, kur_son=33.0, kur_ort=32.0),
            YilKapanis(yil=2025, net_satis=2_000_000.0, brut_kar=300_000.0,
                       net_kar=50_000.0, stok=5_000_000.0, smm=-1_700_000.0,
                       satis_usd=46_000.0, kur_son=43.0, kur_ort=41.0),
        ]

    def test_yillar_sutun_olur(self) -> None:
        csv = yillar_arasi_csv(self._kapanislar())
        self.assertTrue(csv.startswith("Kalem;2024;2025"))
        self.assertIn("--- DOLAR BAZINDA (USD) ---", csv)
        self.assertIn("Net Satışlar;30000,00;46000,00", csv)   # HAM rakam

    def test_kaynak_ve_gizlenen_satir_notu(self) -> None:
        csv = yillar_arasi_csv(self._kapanislar())
        self.assertIn("KAYNAK;", csv)
        self.assertIn("CARİ HESAP HAREKETLERİ", csv)
        self.assertIn("ÇIKARILMIŞTIR", csv)     # model olmayan satırı sormasın

    def test_tek_yil_tablo_uretmez(self) -> None:
        self.assertEqual(yillar_arasi_csv(self._kapanislar()[:1]), "")

    def test_kiyasi_bozan_yillar_isaretlenir(self) -> None:
        k = self._kapanislar()
        k[1].tam = False
        k[0].maliyet_eksik = True
        csv = yillar_arasi_csv(k)
        self.assertIn("2025 yılı TAMAMLANMADI", csv)
        self.assertIn("2024 yılında satışların maliyeti", csv)


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

    def _oran(self, etiket: str, **ek):
        # Kıyas değeri olmayan satır tabloya girmez; iki yıl birebir aynıysa
        # bölümün tamamı düşebilir — o hâlde de satır "yok" demektir.
        _, bolumler = yillar_tablosu([self._yil(2024), self._yil(2025, **ek)])
        oranlar = next(
            (b for b in bolumler if b.baslik == "ORANLAR VE DEVİR HIZLARI"), None)
        if oranlar is None:
            return None
        return next((r for r in oranlar.satirlar if r.etiket == etiket), None)

    def test_stok_oranlari(self) -> None:
        """Kullanıcının en önemli dediği kalem: stok gerçekten dönüyor mu."""
        satir = self._oran("Stok Devir Hızı (kez/yıl)", stok=1_000_000.0)
        self.assertEqual(satir.hucreler, ["4,00", "8,00"])
        self.assertIsNotNone(self._oran("Stok Bekleme Süresi (gün)", stok=1_000_000.0))
        self.assertIsNotNone(self._oran("Stok / Net Satış (%)", stok=1_000_000.0))
        self.assertIsNone(self._oran("Stok Devir Hızı (kez/yıl)", stok=2_000_000.0))

    def test_kredi_borclulugu(self) -> None:
        satir = self._oran("Banka Kredisi / Aktif (%)", banka_kredisi=1_250_000.0)
        self.assertEqual(satir.hucreler, ["20,00", "10,00"])
        self.assertIsNotNone(
            self._oran("Finansman Gideri / Net Satış (%)", finansman_gideri=-600_000.0))
        self.assertIsNotNone(self._oran("Borç / Özkaynak", ozkaynak=8_000_000.0))

    def test_karlilik_oranlari(self) -> None:
        self.assertEqual(
            self._oran("Faaliyet Marjı (%)", faaliyet_kari=2_000_000.0).hucreler,
            ["10,00", "20,00"])
        self.assertIsNotNone(self._oran("Özkaynak Kârlılığı (ROE) (%)", net_kar=1e6))
        self.assertIsNotNone(self._oran("Aktif Kârlılığı (ROA) (%)", net_kar=1e6))

    def test_likidite_ve_tahsilat(self) -> None:
        self.assertIsNotNone(self._oran("Cari Oran", donen=9_000_000.0))
        self.assertIsNotNone(self._oran("Asit-Test", donen=9_000_000.0))
        self.assertIsNotNone(self._oran("Alacak Tahsil Süresi (DSO) (gün)", alacak=5e6))

    def test_maliyet_yoksa_stok_devri_uydurulmaz(self) -> None:
        """SMM girilmemişse devir hızı hesaplanamaz — 0,00 yazmak yanlış olur."""
        satir = self._oran("Stok Devir Hızı (kez/yıl)", smm=0.0, maliyet_eksik=True)
        self.assertEqual(satir.hucreler[-1], "—")
        self.assertIsNotNone(self._oran(
            "Stok / Net Satış (%)", smm=0.0, maliyet_eksik=True, stok=1_000_000.0))

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


class TestKapanissizYil(unittest.TestCase):
    """
    Maliyet kapanışı yapılmamış yılın kâr kalemleri kıyasa girmemeli.

    Canlıda süren yılın brüt marjı %100 çıkıyordu (62 boş) ve tablo bunu
    «Brüt Kâr %+434» diye YEŞİLLE kutluyordu — oysa net satışlar %32 düşmüştü.
    Şişik rakamı kıyaslamaktansa hiç göstermemek doğru.
    """

    @staticmethod
    def _yil(yil: int, *, eksik: bool):
        return YilKapanis(
            yil=yil, net_satis=10_000_000.0, brut_kar=3_000_000.0,
            faaliyet_kari=2_000_000.0, net_kar=1_500_000.0,
            smm=0.0 if eksik else -7_000_000.0, maliyet_eksik=eksik,
            stok=2_000_000.0, alacak=3_000_000.0, ozkaynak=5_000_000.0,
            aktif_toplam=12_000_000.0, donen=7_000_000.0, kvyk=4_000_000.0,
            kur_son=40.0, kur_ort=38.0, satis_usd=260_000.0)

    def test_kar_kalemleri_bos_doner(self) -> None:
        k = self._yil(2026, eksik=True)
        for alan in ("brut_kar", "faaliyet_kari", "net_kar",
                     "brut_marj", "faaliyet_marj", "net_marj", "roe", "roa"):
            self.assertIsNone(k.kalem(alan), alan)

    def test_stok_ayagi_da_bos_doner(self) -> None:
        """
        Eksik «621 SMM / 153 Ticari Mallar» fişinin İKİ ayağı var.

        Eskiden yalnız kâr ayağı eleniyordu; bu test de «stok etkilenmez» diyerek o
        yanlışı sabitliyordu. Canlıda 2026 stoğu 21,5 milyon TL (459 bin USD) görünüp
        «geçen yıla göre %52 arttı» dedi; işlenmemiş ~13,4 milyonluk maliyet düşülünce
        gerçek stok ~8,1 milyon TL (174 bin USD), yani %42 AZALMIŞ çıktı. Yön bile ters.
        """
        k = self._yil(2026, eksik=True)
        for alan in ("stok", "ozkaynak", "aktif_toplam",
                     "stok_satis", "cari_oran", "borc_ozkaynak", "kredi_aktif"):
            self.assertIsNone(k.kalem(alan), alan)

    def test_canli_ayak_maliyetten_bagimsiz_doludur(self) -> None:
        """
        Depodan geçen mal 62'ye hiç bakmaz — kâr satırları «—» olsa da bunlar dolu.

        Kullanıcının kuralı: ilk iki sekme (Bilanço, Gelir Tablosu) resmi kayda dayanır,
        DİĞER HEPSİ canlı veriye. Mukayese tablosu mizandan kurulduğu için maliyet
        işlenmemiş yılda kârlılığın tamamı boşalıyordu; oysa Nakit & Kârlılık sekmesi
        aynı dönemin kârlılığını depodan geçen maldan zaten hesaplıyordu. Kullanıcı
        haklı olarak «bu rakamları bulabiliyorsun, tabloda neden yok?» dedi.
        """
        k = self._yil(2026, eksik=True)
        k.fiili_satis, k.fiili_alis, k.fiili_var = 20_000_000.0, 14_000_000.0, True
        self.assertIsNone(k.kalem("brut_kar"))          # resmi ayak: şişik, gizli
        self.assertEqual(k.kalem("fiili_fark"), 6_000_000.0)
        self.assertAlmostEqual(k.kalem("fiili_marj"), 30.0)

    def test_stok_hareketi_okunamazsa_fiili_ayak_bos(self) -> None:
        """Sıfır satış «marj %0» değil «ölçemedim» demek — uydurmuyoruz."""
        k = self._yil(2026, eksik=True)
        self.assertIsNone(k.kalem("fiili_fark"))
        self.assertIsNone(k.kalem("fiili_marj"))

    def test_smmden_bagimsiz_kalemler_etkilenmez(self) -> None:
        """Nakit, alacak ve satış o fişten geçmez — onları elemek bilgi kaybı olurdu."""
        k = self._yil(2026, eksik=True)
        self.assertEqual(k.kalem("net_satis"), 10_000_000.0)
        self.assertEqual(k.kalem("alacak"), 3_000_000.0)
        self.assertEqual(k.kalem("kvyk"), 4_000_000.0)
        # Asit-Test = (dönen − stok) / KVYK: şişkinlik çıkarmada gider, oran temiz kalır.
        self.assertIsNotNone(k.kalem("asit_test"))

    def test_kapanis_varsa_kar_gorunur(self) -> None:
        k = self._yil(2025, eksik=False)
        self.assertEqual(k.kalem("brut_kar"), 3_000_000.0)
        self.assertIsNotNone(k.kalem("brut_marj"))

    def test_tabloda_sisik_kar_gosterilmez(self) -> None:
        _, bolumler = yillar_tablosu(
            [self._yil(2025, eksik=False), self._yil(2026, eksik=True)])
        satirlar = {r.etiket: r for b in bolumler for r in b.satirlar}
        marj = satirlar.get("Brüt Marj (%)")
        self.assertIsNotNone(marj)
        self.assertEqual(marj.hucreler[-1], "—")          # kapanışsız yıl boş
        self.assertNotEqual(marj.hucreler[0], "—")        # kapanmış yıl dolu

    def test_bos_hucre_yuzde_degisim_uydurmaz(self) -> None:
        _, bolumler = yillar_tablosu(
            [self._yil(2025, eksik=False), self._yil(2026, eksik=True)])
        for b in bolumler:
            for r in b.satirlar:
                if r.hucreler[-1] == "—":
                    self.assertNotIn("%", r.degisim, r.etiket)


class TestMukayeseTablosu(unittest.TestCase):
    """
    Yıllar arası mukayese DETERMİNİSTİK ve YALNIZ DOLAR + ORAN.

    TL bölümü kaldırıldı: yüksek enflasyonda nominal TL kıyası her kalemi "artmış"
    gösterir, hiçbir şey anlatmaz.
    """

    @staticmethod
    def _yillar() -> list[YilKapanis]:
        def mk(yil, satis, usd, kur, kur_o):
            return YilKapanis(
                yil=yil, net_satis=satis, brut_kar=satis * 0.12, net_kar=satis * 0.02,
                smm=-satis * 0.88, stok=140_000.0 * (yil - 2020), alacak=satis * 0.28,
                donen=satis * 0.38, kvyk=satis * 0.4, uvyk=satis * 0.05,
                ozkaynak=satis * 0.15, aktif_toplam=satis * 0.8,
                banka_kredisi=satis * 0.06, borc=satis * 0.12,
                finansman_gideri=-satis * 0.02, satis_usd=usd,
                kur_son=kur, kur_ort=kur_o)
        return [mk(2021, 20_000_000.0, 1_500_430.0, 13.3, 12.0),
                mk(2023, 31_000_000.0, 1_184_243.0, 27.0, 24.0),
                mk(2025, 41_200_000.0, 1_050_163.0, 42.59, 38.0)]

    def _bolum(self, baslik: str, k=None):
        _, bolumler = yillar_tablosu(k or self._yillar())
        return next((b for b in bolumler if b.baslik == baslik), None)

    def _satir(self, baslik: str, etiket: str, k=None):
        bolum = self._bolum(baslik, k)
        return next((r for r in bolum.satirlar if r.etiket == etiket), None)

    def test_tl_bolumu_yok(self) -> None:
        """Nominal TL kıyası yanıltıcı — tablo yalnız dolar ve oranlardan oluşur."""
        _, bolumler = yillar_tablosu(self._yillar())
        self.assertEqual([b.baslik for b in bolumler],
                         ["DOLAR BAZINDA (USD)", "ORANLAR VE DEVİR HIZLARI"])

    def test_tum_yillar_sutun_olur(self) -> None:
        yillar, bolumler = yillar_tablosu(self._yillar())
        self.assertEqual(yillar, [2021, 2023, 2025])
        for bolum in bolumler:
            for satir in bolum.satirlar:
                self.assertEqual(len(satir.hucreler), 3, satir.etiket)

    def test_dolar_bazinda_satis_dususu_gorunur(self) -> None:
        """Kullanıcının asıl istediği: TL'de büyürken dolarda küçülme."""
        satir = self._satir("DOLAR BAZINDA (USD)", "Net Satışlar")
        # Taban ÖNCEKİ YILLARIN ORTALAMASI: (1.500.430 + 1.184.243) / 2 = 1.342.336,5
        # → 1.050.163 %-22. Yalnız ilk yılla kıyaslamak (%-30) tablodaki 2023'ü hiç
        # saymıyordu; kullanıcı «altı yıl var, kıyas iki yıl» dedi.
        self.assertEqual(satir.degisim, "%-22")
        self.assertFalse(satir.iyi)          # dolarda küçülme kötü → kırmızı

    def test_kiyas_tabani_onceki_yillarin_ortalamasi(self) -> None:
        self.assertAlmostEqual(kiyas_tabani([10.0, 20.0, 60.0]), 30.0)
        # Hesaplanamayan yıl ortalamayı bozmaz, sıfır sayılmaz.
        self.assertAlmostEqual(kiyas_tabani([10.0, None, 30.0]), 20.0)
        self.assertIsNone(kiyas_tabani([None, None]))
        self.assertIsNone(kiyas_tabani([]))

    def test_degisim_basligi_neyi_neye_oranladigini_yazar(self) -> None:
        """Başlık «2020→2026» derken aradaki yıllar hesaba girmiyordu — artık yazıyor."""
        self.assertEqual(degisim_basligi([2024, 2025]), "2024→2025")
        self.assertEqual(degisim_basligi([2021, 2023, 2025]), "2025 / önceki ort.")
        self.assertEqual(degisim_basligi([2025]), "")

    def test_iki_sutunda_ortalama_onceki_yilin_kendisidir(self) -> None:
        """Tek geçmiş yıl varsa ortalama o yıldır; davranış değişmemeli."""
        k = self._yillar()[1:]
        _, bolumler = yillar_tablosu(k)
        satir = next(r for b in bolumler for r in b.satirlar if r.etiket == "Net Satışlar")
        self.assertEqual(satir.degisim, "%-11")     # 1.050.163 / 1.184.243 − 1

    def test_kar_kalemleri_ortalama_kurla_cevrilir(self) -> None:
        """Yıl boyunca oluşan tutarı yıl SONU kuruyla bölmek yanlış olurdu."""
        k = self._yillar()
        satir = self._satir("DOLAR BAZINDA (USD)", "Brüt Kâr", k)
        beklenen = k[0].brut_kar / k[0].kur_ort
        self.assertAlmostEqual(float(satir.degerler[0]), beklenen, places=2)

    def test_bakiye_kalemleri_donem_sonu_kuruyla(self) -> None:
        k = self._yillar()
        satir = self._satir("DOLAR BAZINDA (USD)", "Ticari Alacak", k)
        self.assertAlmostEqual(float(satir.degerler[0]), k[0].alacak / k[0].kur_son, places=2)

    def test_tutar_yuzde_oran_puan_degisir(self) -> None:
        """Tutarda yüzde, oranda puan — «cari oran %-33 düştü» yanıltıcı olurdu."""
        self.assertIn("%", self._satir("DOLAR BAZINDA (USD)", "Net Satışlar").degisim)
        self.assertIn("puan", self._satir(
            "ORANLAR VE DEVİR HIZLARI", "Stok / Net Satış (%)").degisim)

    def test_borc_artisi_kotu_satis_artisi_iyi(self) -> None:
        """Yön anlamı kaleme göre değişir: satış artışı iyi, borç artışı kötü."""
        k = self._yillar()
        for i, y in enumerate(k):          # dolar bazında da katlanarak artsın
            y.kvyk = 10_000_000.0 * (10 ** i)
        self.assertFalse(self._satir("DOLAR BAZINDA (USD)", "Kısa Vadeli Borç", k).iyi)
        self.assertTrue(self._satir("ORANLAR VE DEVİR HIZLARI", "Net Marj (%)",
                                    self._kar_artan()).iyi)

    @staticmethod
    def _kar_artan() -> list[YilKapanis]:
        return [YilKapanis(yil=y, net_satis=1_000_000.0, net_kar=10_000.0 * (y - 2020),
                           satis_usd=30_000.0, kur_son=33.0, kur_ort=32.0)
                for y in (2021, 2023, 2025)]

    def test_negatif_hucreler_isaretlenir(self) -> None:
        """Kırmızıya boyanacak hücreleri görünüm değil domain belirler."""
        k = self._yillar()
        for i, y in enumerate(k):
            y.ozkaynak = -8_484.0 * (i + 1)
        satir = self._satir("DOLAR BAZINDA (USD)", "Özkaynak", k)
        self.assertEqual(satir.eksi, [True, True, True])

    def test_birim_acik_yazilir(self) -> None:
        """«B» Türkçede milyar diye okunuyordu; 650 bin ile 650 milyar karışıyordu."""
        from domain.ai_yorum import _kisa
        self.assertEqual(_kisa(2_400_000_000.0), "2,4 milyar")
        self.assertEqual(_kisa(41_200_000.0), "41,2 milyon")
        self.assertNotIn("M", _kisa(41_200_000.0))

    def test_milyon_alti_tam_yazilir(self) -> None:
        """«176 bin» yuvarlaması farklı yılları aynı gösteriyordu — kullanıcı fark etti."""
        from domain.ai_yorum import _kisa
        self.assertEqual(_kisa(42.61), "43")
        self.assertNotEqual(_kisa(176_270.38), _kisa(176_100.0))
        self.assertEqual(_kisa(176_270.38), "176.270")

    # ------------------------------------------------ kıyas değeri olmayan satırlar
    def test_hic_kipirdamayan_satir_gosterilmez(self) -> None:
        """
        «Hepsi aynı» bir karşılaştırma değildir.

        Önce uyarı işaretiyle gösteriliyordu; kullanıcı «mal gibi uyarı yapacağımıza
        kapatalım» dedi — haklı, tabloyu kalabalıklaştırıyordu.
        """
        k = self._yillar()
        for y in k:
            y.stok = 139_999.18          # canlıda beş yıl kuruşu kuruşuna aynıydı
        etiketler = [r.etiket for r in self._bolum("DOLAR BAZINDA (USD)", k).satirlar]
        self.assertNotIn("Stok", etiketler)
        self.assertIn("Ticari Alacak", etiketler)   # gerçekten değişen kalır

    def test_dolar_satiri_TL_kaynagina_bakar(self) -> None:
        """
        TL'de sabit kalem, kur değiştiği için dolarda oynuyormuş gibi görünür.

        Aynı boş bilginin kılık değiştirmiş hâli — kullanıcı canlıda fark etti.
        """
        k = self._yillar()
        for y in k:
            y.banka_kredisi = 16_230.0   # TL sabit, kur her yıl farklı
        etiketler = [r.etiket for r in self._bolum("DOLAR BAZINDA (USD)", k).satirlar]
        self.assertNotIn("Banka Kredisi", etiketler)

    def test_kurus_farkiyla_kipirdayan_da_gizlenir(self) -> None:
        """Birebir eşitlik aramak yetmiyordu; ölçüt yayılım (%0,5)."""
        k = self._yillar()
        for y, deger in zip(k, (176_100.0, 176_270.38, 176_290.0), strict=True):
            y.aktif_toplam = deger
        etiketler = [r.etiket for r in self._bolum("DOLAR BAZINDA (USD)", k).satirlar]
        self.assertNotIn("Aktif Toplam", etiketler)

    def test_hepsi_sifir_satir_gizlenir(self) -> None:
        """Hiç kaydı olmayan kalem tabloda yer kaplamamalı."""
        k = self._yillar()
        for y in k:
            y.uvyk = 0.0
        etiketler = [r.etiket for r in self._bolum("DOLAR BAZINDA (USD)", k).satirlar]
        self.assertNotIn("Uzun Vadeli Borç", etiketler)

    def test_hic_hesaplanamayan_oran_gizlenir(self) -> None:
        k = self._yillar()
        for y in k:
            y.ozkaynak = -1.0            # ROE her yıl hesaplanamaz
        etiketler = [r.etiket for r in self._bolum("ORANLAR VE DEVİR HIZLARI", k).satirlar]
        self.assertNotIn("Özkaynak Kârlılığı (ROE) (%)", etiketler)

    def test_bos_bolum_hic_eklenmez(self) -> None:
        """Tüm satırları elenen bölüm başlık olarak kalmamalı."""
        k = [YilKapanis(yil=y, net_satis=1_000_000.0, aktif_toplam=5_000_000.0,
                        satis_usd=30_000.0, kur_son=33.0, kur_ort=32.0) for y in (2024, 2025)]
        _, bolumler = yillar_tablosu(k)
        for b in bolumler:
            self.assertTrue(b.satirlar, f"{b.baslik} boş kalmış")

    def test_kur_yoksa_dolar_bolumu_hic_gelmez(self) -> None:
        k = self._yillar()
        k[1].kur_son = 0.0
        _, bolumler = yillar_tablosu(k)
        self.assertNotIn("DOLAR BAZINDA (USD)", [b.baslik for b in bolumler])
        self.assertIn("ORANLAR VE DEVİR HIZLARI", [b.baslik for b in bolumler])

    def test_tek_yilda_tablo_yok(self) -> None:
        self.assertEqual(yillar_tablosu(self._yillar()[:1]), ([], []))

    def test_veritabaninda_olmayan_yil_dolu_degil(self) -> None:
        """Boş yılın sorgusu hata değil sıfır döner; tabloya girerse trend uydurulur."""
        self.assertFalse(YilKapanis(yil=2019).dolu)
        self.assertTrue(YilKapanis(yil=2025, net_satis=1.0).dolu)
        self.assertTrue(YilKapanis(yil=2025, alacak=1.0).dolu)

    def test_gecikme_orani(self) -> None:
        k = YilKapanis(yil=2025, alacak=11_358_890.0, alacak_gecikmis=7_602_854.0)
        self.assertAlmostEqual(k.gecikme_orani, 66.93, places=1)
        self.assertIsNone(YilKapanis(yil=2025).gecikme_orani)

    def test_csv_mukayeseyi_icerir(self) -> None:
        """Excel'de kendi grafiğini çizebilsin diye CSV'ye de girer — ham rakamla."""
        csv = ai_yorum_csv(AiYorum(yil=2025, bas="2025-01-01", bit="2025-12-31",
                                   kapsam_bas="2021-01-01", kapanislar=self._yillar()))
        self.assertIn("MUKAYESE;Kalem;2021;2023;2025;2025 / önceki ort.", csv)
        self.assertIn("MUKAYESE;Net Satışlar;1500430,00;1184243,00;1050163,00", csv)

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
    """Yüksek enflasyonda düz TL kıyası yanıltır — tablo dolar üzerinden kurulur."""

    @staticmethod
    def _kapanislar(kur_2023: float = 27.0, kur_2025: float = 42.3) -> list[YilKapanis]:
        return [
            YilKapanis(yil=2023, net_satis=27_000_000.0, stok=8_000_000.0,
                       alacak=6_000_000.0, satis_usd=1_000_000.0,
                       kur_son=kur_2023, kur_ort=kur_2023 * 0.9),
            YilKapanis(yil=2025, net_satis=41_200_000.0, stok=12_000_000.0,
                       alacak=11_360_000.0, satis_usd=800_000.0,
                       kur_son=kur_2025, kur_ort=kur_2025 * 0.9),
        ]

    def _bolum(self, k=None):
        _, bolumler = yillar_tablosu(k or self._kapanislar())
        return next((b for b in bolumler if b.baslik == "DOLAR BAZINDA (USD)"), None)

    def test_doviz_blogu_kurulur(self) -> None:
        satirlar = {r.etiket: r for r in self._bolum().satirlar}
        self.assertEqual(satirlar["TL/USD kuru (dönem sonu)"].hucreler, ["27,00", "42,30"])
        self.assertEqual(satirlar["Net Satışlar"].hucreler, ["1,0 milyon", "800.000"])

    def test_stok_ve_alacak_dolara_cevrilir(self) -> None:
        """Kullanıcının işaret ettiği yer: stok/alacakta nominal TL en çok yanıltır."""
        satirlar = {r.etiket: r for r in self._bolum().satirlar}
        self.assertEqual(satirlar["Stok"].hucreler, ["296.296", "283.688"])  # TL'de arttı
        self.assertEqual(satirlar["Stok"].degisim, "%-4")                     # USD'de düştü

    def test_kur_yoksa_blok_hic_yazilmaz(self) -> None:
        """Güvenilir kur olmadan uydurma dolar rakamı vermektense hiç verme."""
        k = self._kapanislar()
        k[1].kur_son = 0.0
        self.assertIsNone(self._bolum(k))

    def test_usd_kursuz_bos_doner(self) -> None:
        """Kur yoksa 0,00 yazmak «dolar karşılığı sıfır» demek olurdu — hücre boş kalır."""
        self.assertIsNone(YilKapanis(yil=2025).usd(1_000.0))
        self.assertIsNone(YilKapanis(yil=2025).usd_akis(1_000.0))

    def test_ortalama_kur_yoksa_donem_sonuna_duser(self) -> None:
        k = YilKapanis(yil=2025, kur_son=40.0)
        self.assertAlmostEqual(k.usd_akis(4_000.0), 100.0)

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
