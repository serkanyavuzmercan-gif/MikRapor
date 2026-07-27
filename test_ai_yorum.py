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
    ai_yorum_csv,
    build_ai_veri_paketi,
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
        for beklenen in ("anthropic", "openai", "google", "deepseek", "groq", "xai", "ozel"):
            self.assertIn(beklenen, kodlar)

    def test_bilinmeyen_kod_varsayilana_duser(self) -> None:
        self.assertEqual(saglayici_bul("yok-boyle").kod, "anthropic")

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
            "Özet", "İyi Giden 3 Şey", "Dikkat Edilmesi Gereken 3 Şey", "Bu Ay Yapılacak 3 İş")}
        self.assertEqual(len(renkler), 4)

    def test_zaman_asimi_ve_baglanti(self) -> None:
        self.assertIn("zaman aşımı", ag_hata_mesaji(TimeoutError()).lower())
        self.assertIn("adres çözümlenemedi", ag_hata_mesaji(
            urllib.error.URLError("Name or service not known")).lower())
        self.assertIn("ssl", ag_hata_mesaji(
            urllib.error.URLError("certificate verify failed")).lower())


class TestOpenAiUyumluYol(unittest.TestCase):
    """Groq/Gemini/DeepSeek/xAI tek şemadan geçer — istek gövdesi doğru kurulmalı."""

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
        cfg = AiConfig(saglayici="groq", api_key="gsk_test", onay=True)
        with patch("urllib.request.urlopen", self._sahte_yanit(yakalanan)), \
                patch("infra.ai_client.guncel_model_sec", return_value="bir-model"):
            y = yorumla(cfg, _paket())
        self.assertEqual(yakalanan["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(yakalanan["auth"], "Bearer gsk_test")
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
                       "## Bu Ay Yapılacak 3 İş", "## Veride Göremediklerim"):
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
