"""
Yıllar arası mukayese çekimi — hangi yılın hangi veritabanından okunduğu.

Mikro auth gövdesinde CalismaYili gider ve sunucu isteği O YILIN veritabanına
yönlendirir. Tek istemciyle geçmiş yılları sorgulamak, tarih süzgeci doğru olsa bile
hep aynı veritabanını okur — canlıda 2021 ile 2025 bilançosu kuruşu kuruşuna aynı
çıkıyordu. Bu dosya o kuralı sabitler.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from infra.config import MikroConfig
from infra.mukayese_fetch import yil_client, yillari_cek

_CFG = MikroConfig(
    base_url="https://ornek.local", api_key="k", firma_kodu="20",
    calisma_yili=2025, kullanici_kodu="u", sifre_gun="s",
)


class TestYilClient(unittest.TestCase):
    def test_calisma_yili_yilin_kendisi_olur(self) -> None:
        c = yil_client(_CFG, 2021)
        self.assertEqual(c.cfg.calisma_yili, 2021)

    def test_diger_ayarlar_korunur(self) -> None:
        c = yil_client(_CFG, 2022)
        self.assertEqual(c.cfg.firma_kodu, "20")
        self.assertEqual(c.cfg.api_key, "k")
        self.assertEqual(c.cfg.base_url, "https://ornek.local")

    def test_kaynak_cfg_degismez(self) -> None:
        yil_client(_CFG, 2021)
        self.assertEqual(_CFG.calisma_yili, 2025)   # replace kopya üretir


class TestYillariCek(unittest.TestCase):
    """Her geçmiş yıl KENDİ çalışma yılıyla sorgulanmalı."""

    def setUp(self) -> None:
        self.sorgulanan: list[int] = []

        def sahte_kapanis(client, yil, **kw):
            self.sorgulanan.append(client.cfg.calisma_yili)
            from domain.ai_yorum import YilKapanis
            return YilKapanis(yil=yil, net_satis=1_000_000.0 * yil)

        self.yama = patch("infra.mukayese_fetch.yil_kapanisi", side_effect=sahte_kapanis)
        self.yama.start()
        self.addCleanup(self.yama.stop)
        # Vade planı ağa çıkmasın.
        v = patch("infra.mukayese_fetch.fetch_cari_vade_gun", return_value={})
        v.start()
        self.addCleanup(v.stop)

    def test_her_yil_kendi_veritabanindan(self) -> None:
        yillari_cek(_CFG, [2021, 2022, 2023])
        self.assertEqual(self.sorgulanan, [2021, 2022, 2023])

    def test_odak_yil_verilen_istemciyi_kullanir(self) -> None:
        """Odak yılın verisi zaten çekilmiş olur; yeniden bağlanmak israf."""
        odak = yil_client(_CFG, 2025)
        yillari_cek(_CFG, [2024, 2025], odak_client=odak)
        self.assertEqual(self.sorgulanan, [2024, 2025])

    def test_bos_yil_listesi(self) -> None:
        self.assertEqual(yillari_cek(_CFG, []), [])

    def test_veritabani_yoksa_yil_atlanir(self) -> None:
        from infra.mikro_api import MikroAPIError

        def bazen_patla(client, yil, **kw):
            if yil == 2022:
                raise MikroAPIError("veritabanı yok")
            from domain.ai_yorum import YilKapanis
            return YilKapanis(yil=yil, net_satis=1_000_000.0)

        self.yama.stop()
        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=bazen_patla):
            out = yillari_cek(_CFG, [2021, 2022, 2023])
        self.assertEqual([k.yil for k in out], [2021, 2023])
        self.yama.start()

    def test_bos_yil_tabloya_girmez(self) -> None:
        """Veri dönmeyen yıl sıfır satırı olarak eklenirse trend uydurulur."""
        from domain.ai_yorum import YilKapanis

        def bos_2022(client, yil, **kw):
            return YilKapanis(yil=yil) if yil == 2022 else YilKapanis(
                yil=yil, net_satis=5_000_000.0)

        self.yama.stop()
        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=bos_2022):
            out = yillari_cek(_CFG, [2021, 2022, 2023])
        self.assertEqual([k.yil for k in out], [2021, 2023])
        self.yama.start()


if __name__ == "__main__":
    unittest.main()
