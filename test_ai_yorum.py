"""Yapay Zekâ Yorumu — ayar/onay kapısı, veri paketi ve yorum ayrıştırma testleri."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from domain.ai_yorum import (
    SISTEM_PROMPT,
    AiYorum,
    ai_yorum_csv,
    build_ai_veri_paketi,
)
from infra.ai_client import MAX_GIRDI_KARAKTER, AiHata, yorumla
from infra.ai_config import VARSAYILAN_MODEL, AiConfig


def _paket(bolumler=None):
    return build_ai_veri_paketi(
        yil=2026, bas="2026-01-01", bit="2026-12-31", firma="TEST A.Ş.",
        bolumler=bolumler if bolumler is not None else [("BİLANÇO", "Bölüm;Kalem;Tutar\nAKTİF;Nakit;1.000")],
    )


class TestAiConfig(unittest.TestCase):
    def test_hazir_icin_ikisi_de_sart(self) -> None:
        self.assertFalse(AiConfig().hazir)
        self.assertFalse(AiConfig(api_key="sk-ant-x").hazir)          # onay yok
        self.assertFalse(AiConfig(onay=True).hazir)                    # anahtar yok
        self.assertTrue(AiConfig(api_key="sk-ant-x", onay=True).hazir)

    def test_eksik_sebebi_anlasilir(self) -> None:
        self.assertIn("anahtar", AiConfig().eksik().lower())
        self.assertIn("onay", AiConfig(api_key="sk-ant-x").eksik().lower())
        self.assertEqual(AiConfig(api_key="sk-ant-x", onay=True).eksik(), "")

    def test_bilinmeyen_model_varsayilana_duser(self) -> None:
        self.assertEqual(AiConfig(model="gpt-uydurma").normalized().model, VARSAYILAN_MODEL)
        self.assertEqual(AiConfig(model="").normalized().model, VARSAYILAN_MODEL)

    def test_onay_geri_alinabilir(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        self.assertTrue(cfg.hazir)
        cfg.onay = False
        self.assertFalse(cfg.hazir)  # anahtar dursa da çağrı yapılamaz


class TestOnaySizAgaCikilmaz(unittest.TestCase):
    """En kritik davranış: onay/anahtar yoksa HİÇBİR ağ çağrısı olmamalı."""

    def test_onay_yoksa_istemci_hic_kurulmaz(self) -> None:
        with patch("infra.ai_client._istemci") as sahte:
            for cfg in (AiConfig(), AiConfig(api_key="sk-ant-x"), AiConfig(onay=True)):
                with self.assertRaises(AiHata):
                    yorumla(cfg, _paket())
            sahte.assert_not_called()

    def test_bos_paket_gonderilmez(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        with patch("infra.ai_client._istemci") as sahte:
            with self.assertRaises(AiHata):
                yorumla(cfg, _paket(bolumler=[]))
            sahte.assert_not_called()

    def test_asiri_buyuk_paket_sessizce_kirpilmaz(self) -> None:
        cfg = AiConfig(api_key="sk-ant-x", onay=True)
        dev = _paket(bolumler=[("BÜYÜK", "x" * (MAX_GIRDI_KARAKTER + 10))])
        with patch("infra.ai_client._istemci") as sahte:
            with self.assertRaises(AiHata) as ctx:
                yorumla(cfg, dev)
            self.assertIn("büyük", str(ctx.exception).lower())
            sahte.assert_not_called()


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
