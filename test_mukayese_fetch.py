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

    def test_katalog_kurulamazsa_secili_firmayla_devam(self) -> None:
        """
        Katalog yoklaması düşerse rapor DURMAMALI.

        Yıl → veritabanı eşlemesi kurulamadığında seçenek zaten tek: seçili firma.
        «Yanlışını seçmek» diye bir şey yok. Burada durmak, geçici bir ağ hatasında
        programı komple kullanılamaz yapardı — canlıda iki yıl seçilmesine rağmen
        mukayesenin hiç çıkmaması sorunu tam da böyle doğmuştu.
        """
        from domain.ai_yorum import YilKapanis
        from infra.mikro_api import MikroAPIError

        kullanilan: list[str] = []

        def kapanis(client, yil, **kw):
            kullanilan.append(client.cfg.firma_kodu)
            return YilKapanis(yil=yil, net_satis=7_000_000.0)

        self.yama.stop()
        with patch("infra.veritabani.fetch_yil_araligi",
                   side_effect=MikroAPIError("yoklama düştü")), \
                patch("infra.mukayese_fetch.yil_kapanisi", side_effect=kapanis):
            out = yillari_cek(_CFG, [2024, 2025])
        self.yama.start()

        self.assertEqual([k.yil for k in out], [2024, 2025])   # tablo kurulabildi
        self.assertEqual(set(kullanilan), {_CFG.firma_kodu})   # seçili firma kullanıldı

    def test_yil_bazli_db_varsa_yedege_dusulmez(self) -> None:
        from domain.ai_yorum import YilKapanis
        denenen: list[int] = []

        def hepsi_var(client, yil, **kw):
            denenen.append(client.cfg.calisma_yili)
            return YilKapanis(yil=yil, net_satis=3_000_000.0)

        self.yama.stop()
        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=hepsi_var):
            yillari_cek(_CFG, [2023, 2024, 2025])
        self.yama.start()
        self.assertEqual(denenen, [2023, 2024, 2025])   # yedek hiç denenmedi

    def test_veritabani_yoksa_yil_atlanir(self) -> None:
        from infra.mikro_api import MikroAPIError

        def bazen_patla(client, yil, **kw):
            if yil == 2022:      # hem kendi yılında hem yedekte patlar
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
            # 2022 her iki yolda da boş döner → tabloya girmemeli
            return YilKapanis(yil=yil) if yil == 2022 else YilKapanis(
                yil=yil, net_satis=5_000_000.0)

        self.yama.stop()
        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=bos_2022):
            out = yillari_cek(_CFG, [2021, 2022, 2023])
        self.assertEqual([k.yil for k in out], [2021, 2023])
        self.yama.start()


class TestAyniGunePencere(unittest.TestCase):
    """
    Devam eden yılla kıyas AYNI PENCEREDEN yapılmalı.

    Canlıda 27.07.2025–28.07.2026 seçilmişken 2025 sütunu 12 aylık, 2026 sütunu
    7 aylıktı; ciro «%59 düştü» görünüyordu. Kullanıcı haklı olarak "1,1 milyon USD
    ciroyu ilk 7 ayda yapmış olamayız" dedi — gerçekten de o rakam tam 2025'ti.
    """

    def test_odak_yil_surerken_gecmis_yil_ayni_gune_kirpilir(self) -> None:
        from infra.mukayese_fetch import ayni_gune_kirp
        self.assertEqual(ayni_gune_kirp(2025, "2026-07-28"), ("2025-07-28", False))

    def test_odak_yil_tamsa_hepsi_tam_yil(self) -> None:
        from infra.mukayese_fetch import ayni_gune_kirp
        self.assertEqual(ayni_gune_kirp(2024, "2025-12-31"), ("2024-12-31", True))

    def test_odak_bit_yoksa_tam_yil(self) -> None:
        from infra.mukayese_fetch import ayni_gune_kirp
        self.assertEqual(ayni_gune_kirp(2024, ""), ("2024-12-31", True))

    def test_29_subat_olmayan_yila_kirpilir(self) -> None:
        """2028 artık yıl, 2027 değil — geçersiz tarih üretilmemeli."""
        from infra.mukayese_fetch import ayni_gune_kirp
        self.assertEqual(ayni_gune_kirp(2027, "2028-02-29"), ("2027-02-28", False))

    def test_gecmis_yil_kirpilmis_pencereden_okunur(self) -> None:
        from infra.mukayese_fetch import yillari_cek
        pencere: list[tuple[int, str, bool]] = []

        def sahte(client, yil, **kw):
            from domain.ai_yorum import YilKapanis
            pencere.append((yil, kw.get("bit") or "", kw.get("tam", True)))
            return YilKapanis(yil=yil, net_satis=1_000_000.0)

        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=sahte), \
                patch("infra.mukayese_fetch.fetch_cari_vade_gun", return_value={}):
            yillari_cek(_CFG, [2025, 2026], odak_bit="2026-07-28", odak_tam=False)
        self.assertEqual(pencere[0], (2025, "2025-07-28", False))    # geçmiş yıl
        self.assertEqual(pencere[-1][:2], (2026, "2026-07-28"))      # odak yıl


class TestDonemParcalama(unittest.TestCase):
    """
    AKIŞ raporları dönem iki veritabanına yayıldığında parçalanmalı.

    Canlıda 20 (2020-2025) ve 26 (2026+) ayrı veritabanı. 01.07.2025–30.06.2026
    seçilince gelir tablosu/nakit akış tek istemciyle okunuyordu: 2025 yarısı
    sessizce kayboluyordu. BAKİYE sorguları ise bölünemez — tek bir tarihe aitler.
    """

    def setUp(self) -> None:
        self.yama = patch(
            "infra.mukayese_fetch.yil_client",
            side_effect=lambda _cfg, yil: f"istemci-{yil}")
        self.yama.start()
        self.addCleanup(self.yama.stop)

    def test_satirlar_her_yilin_istemcisinden_birlestirilir(self) -> None:
        from infra.mukayese_fetch import donem_satirlari
        out = donem_satirlari(
            _CFG, "2025-07-28", "2026-07-28",
            lambda c, b, e: [{"c": c, "bas": b, "bit": e}])
        self.assertEqual(out, [
            {"c": "istemci-2025", "bas": "2025-07-28", "bit": "2025-12-31"},
            {"c": "istemci-2026", "bas": "2026-01-01", "bit": "2026-07-28"},
        ])

    def test_tek_yilda_tek_cagri(self) -> None:
        """Tek veritabanlı kurulum eskisi gibi çalışsın — fazladan sorgu yok."""
        from infra.mukayese_fetch import donem_satirlari
        cagrilar: list[str] = []
        donem_satirlari(_CFG, "2026-01-01", "2026-06-30",
                        lambda c, _b, _e: cagrilar.append(c) or [])
        self.assertEqual(cagrilar, ["istemci-2026"])

    def test_toplam_parcalarin_toplamidir(self) -> None:
        from infra.mukayese_fetch import donem_toplami
        self.assertEqual(
            donem_toplami(_CFG, "2025-07-28", "2026-07-28", lambda _c, _b, _e: 1500.0),
            3000.0)

    def test_ilerleme_yalniz_cok_parcali_donemde_bildirilir(self) -> None:
        from infra.mukayese_fetch import donem_satirlari
        tek: list[str] = []
        donem_satirlari(_CFG, "2026-01-01", "2026-06-30", lambda *_: [],
                        bildir=tek.append)
        cok: list[str] = []
        donem_satirlari(_CFG, "2025-07-28", "2026-07-28", lambda *_: [],
                        bildir=cok.append, ad="nakit hareketleri")
        self.assertEqual(tek, [])
        self.assertEqual(len(cok), 2)
        self.assertIn("2025 veritabanından nakit hareketleri", cok[0])

    def test_hareketler_dort_akisi_da_birlestirir(self) -> None:
        from infra.mukayese_fetch import donem_hareketleri
        with patch("infra.mukayese_fetch.fetch_stok_ozet",
                   side_effect=lambda c, _b, _e: [{"stok": c}]), \
                patch("infra.mukayese_fetch.fetch_stok_aylik",
                      side_effect=lambda c, _b, _e: [{"stok_ay": c}]), \
                patch("infra.mukayese_fetch.fetch_nakit_ozet_ve_aylik",
                      side_effect=lambda c, _b, _e: ([{"nakit": c}], [{"nakit_ay": c}])):
            stok, stok_aylik, nakit, nakit_aylik = donem_hareketleri(
                _CFG, "2025-07-28", "2026-07-28")
        bekle = ["istemci-2025", "istemci-2026"]
        self.assertEqual([r["stok"] for r in stok], bekle)
        self.assertEqual([r["stok_ay"] for r in stok_aylik], bekle)
        self.assertEqual([r["nakit"] for r in nakit], bekle)
        self.assertEqual([r["nakit_ay"] for r in nakit_aylik], bekle)


class TestBakiyeBolunmez(unittest.TestCase):
    """
    Fotoğraf sorguları bitişin veritabanından okunur; yıllara bölünmemeli.

    Mizanı ya da kapanış nakdini parçalayıp toplamak bakiyeyi ikiye katlar.
    Bu test o çağrıların `donem_satirlari`/`donem_toplami`'ya taşınmasını engeller.
    """

    _BAKIYE = ("fetch_mizan", "fetch_cari_bakiye", "fetch_nakit_bakiye_gl",
               "fetch_bakiye_ozet", "fetch_acik_kalemler", "fetch_cari_vade_gun",
               "fetch_kredi_karti_borclari", "fetch_kredi_taksitleri")

    def test_hicbir_sekme_bakiyeyi_parcalamaz(self) -> None:
        import re
        from pathlib import Path
        desen = re.compile(
            r"donem_(?:satirlari|toplami)\([^)]*?(" + "|".join(self._BAKIYE) + r")\b",
            re.S)
        for yol in sorted(Path("ui/tabs").glob("*_tab.py")):
            bulgu = desen.search(yol.read_text(encoding="utf-8"))
            self.assertIsNone(
                bulgu,
                f"{yol.name}: bakiye sorgusu ({bulgu.group(1) if bulgu else ''}) "
                "yıllara bölünemez — bitişin veritabanından okunmalı.")


if __name__ == "__main__":
    unittest.main()
