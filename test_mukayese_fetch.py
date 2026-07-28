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
        yillari_cek(_CFG, "2021-01-01", "2023-12-31")
        self.assertEqual(self.sorgulanan, [2021, 2022, 2023])

    def test_odak_yil_verilen_istemciyi_kullanir(self) -> None:
        """Odak yılın verisi zaten çekilmiş olur; yeniden bağlanmak israf."""
        odak = yil_client(_CFG, 2025)
        yillari_cek(_CFG, "2024-01-01", "2025-12-31", odak_client=odak)
        self.assertEqual(self.sorgulanan, [2024, 2025])

    def test_bos_yil_listesi(self) -> None:
        with self.assertRaises(ValueError):
            yillari_cek(_CFG, "2026-12-31", "2026-01-01")

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
            out = yillari_cek(_CFG, "2024-01-01", "2025-12-31")
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
            yillari_cek(_CFG, "2023-01-01", "2025-12-31")
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
            out = yillari_cek(_CFG, "2021-01-01", "2023-12-31")
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
            out = yillari_cek(_CFG, "2021-01-01", "2023-12-31")
        self.assertEqual([k.yil for k in out], [2021, 2023])
        self.yama.start()


class TestSecilenAralikKutsal(unittest.TestCase):
    """
    SEÇİLEN TARİH ARALIĞININ DIŞINDAN TEK GÜN OKUNMAZ.

    Önce her yıl 1 Ocak'tan okunuyordu; gerekçe «yıl kıyası aynı pencereden yapılmalı»
    idi ve kendi içinde tutarlıydı. Ama kullanıcının seçimini eziyordu: 28.07.2025
    seçilmişken tabloya 01.01.2025 verisi giriyordu. Kullanıcı bunu net biçimde
    reddetti — «tarih aralığı kutsal, her şeyi o belirliyor». Sütun artık o yılın
    seçili aralıkla KESİŞİMİDİR; hesaplanamayan hücre «—» kalır.
    """

    @staticmethod
    def _pencereler(bas: str, bit: str) -> list[tuple[int, str, str]]:
        from domain.ai_yorum import YilKapanis
        from infra.mukayese_fetch import yillari_cek
        gorulen: list[tuple[int, str, str]] = []

        def sahte(client, yil, **kw):
            gorulen.append((yil, kw.get("bas") or "", kw.get("bit") or ""))
            return YilKapanis(yil=yil, net_satis=1_000_000.0)

        with patch("infra.mukayese_fetch.yil_kapanisi", side_effect=sahte), \
                patch("infra.mukayese_fetch.fetch_cari_vade_gun", return_value={}):
            yillari_cek(_CFG, bas, bit)
        return gorulen

    def test_her_sutun_araligin_kendi_parcasidir(self) -> None:
        """28.07.2025–28.07.2026 → 2025 sütunu 28.07–31.12, 2026 sütunu 01.01–28.07."""
        self.assertEqual(
            self._pencereler("2025-07-28", "2026-07-28"),
            [(2025, "2025-07-28", "2025-12-31"),
             (2026, "2026-01-01", "2026-07-28")],
        )

    def test_aralik_disina_tek_gun_tasilmaz(self) -> None:
        for yil, p_bas, p_bit in self._pencereler("2025-07-28", "2026-07-28"):
            self.assertGreaterEqual(p_bas, "2025-07-28", yil)
            self.assertLessEqual(p_bit, "2026-07-28", yil)

    def test_tam_yillar_tam_isaretlenir(self) -> None:
        """Aralık yılın tamamını kapsıyorsa sütun «tam» sayılır, başlıkta gün yazmaz."""
        self.assertEqual(
            self._pencereler("2024-01-01", "2025-12-31"),
            [(2024, "2024-01-01", "2024-12-31"),
             (2025, "2025-01-01", "2025-12-31")],
        )

    def test_tam_bayragi_pencereden_turetilir(self) -> None:
        """«tam» elle verilmez, pencereden türer: 01.01–31.12 ise tam, değilse kısmi."""
        from infra.mukayese_fetch import tam_yil
        self.assertTrue(tam_yil("2025-01-01", "2025-12-31"))
        self.assertFalse(tam_yil("2025-07-28", "2025-12-31"))
        self.assertFalse(tam_yil("2026-01-01", "2026-07-28"))

    def test_sutun_basligi_gercek_pencereyi_gosterir(self) -> None:
        from domain.ai_yorum import YilKapanis
        kismi = YilKapanis(yil=2025, bas="2025-07-28", bit="2025-12-31", tam=False)
        self.assertEqual(kismi.basligi(), "2025 (28.07–31.12)")
        self.assertEqual(
            YilKapanis(yil=2024, bas="2024-01-01", bit="2024-12-31").basligi(), "2024")


class TestGecenYilAyniDonem(unittest.TestCase):
    """
    Kullanıcı AÇIKÇA isterse geçen yılın aynı dönemi gelir — kural bozulmadan.

    Takvim yılına bölünmüş sütunlar farklı uzunlukta olabiliyor: canlıda 2025 sütunu
    5 ay, 2026 sütunu 7 aydı ve tablo «%+4 büyüme» gösteriyordu. Aylığa indirilince
    satış %25 DÜŞMÜŞTÜ. Eşit uzunlukta iki pencere olmadan akış kalemleri kıyaslanamaz.

    Fark şurada: program kendi kafasına göre aralık dışına çıkmıyor, kullanıcı istediği
    için çıkıyor ve ne geldiği sütun başlığında yazıyor.
    """

    def test_donem_aynen_bir_yil_geri_kayar(self) -> None:
        from infra.mukayese_fetch import onceki_donem
        self.assertEqual(onceki_donem("2025-07-28", "2026-07-28"),
                         ("2024-07-28", "2025-07-28"))

    def test_iki_pencere_esit_uzunlukta(self) -> None:
        from datetime import date

        from infra.mukayese_fetch import onceki_donem
        bas, bit = "2025-07-28", "2026-07-28"
        o_bas, o_bit = onceki_donem(bas, bit)
        gun = (date.fromisoformat(bit) - date.fromisoformat(bas)).days
        o_gun = (date.fromisoformat(o_bit) - date.fromisoformat(o_bas)).days
        self.assertLessEqual(abs(gun - o_gun), 1)   # yalnız artık gün farkı

    def test_29_subat_gecerli_tarihe_iner(self) -> None:
        from infra.mukayese_fetch import onceki_donem
        self.assertEqual(onceki_donem("2024-02-29", "2024-06-30"),
                         ("2023-02-28", "2023-06-30"))

    def test_yila_yayilan_sutun_basliginda_yil_da_yazar(self) -> None:
        """«28.07–28.07» iki farklı yılı gösteremez; başlık tam tarih yazmalı."""
        from domain.ai_yorum import YilKapanis
        k = YilKapanis(yil=2026, bas="2025-07-28", bit="2026-07-28", tam=False)
        self.assertEqual(k.basligi(), "28.07.2025–28.07.2026")

    def test_donem_kapanisi_akisi_boler_bakiyeyi_bolmez(self) -> None:
        """Dönem iki veritabanına yayılsa da akış birleşir, bakiye bitişten okunur."""
        from infra.mukayese_fetch import donem_kapanisi
        akis_pencereleri: list[tuple[str, str]] = []
        mizan_gunleri: list[str] = []

        def gelir(client, b, e):
            akis_pencereleri.append((b, e))
            return []

        with patch("infra.mukayese_fetch.yil_client", side_effect=lambda _c, y: f"c{y}"), \
                patch("infra.mukayese_fetch.fetch_gelir_tablosu", side_effect=gelir), \
                patch("infra.mukayese_fetch.fetch_stok_ozet", return_value=[]), \
                patch("infra.mukayese_fetch.fetch_mizan",
                      side_effect=lambda c, g: mizan_gunleri.append(g) or []), \
                patch("infra.mukayese_fetch.fetch_acik_kalemler", return_value=[]), \
                patch("infra.mukayese_fetch.fetch_cari_vade_gun", return_value={}), \
                patch("infra.mukayese_fetch.fetch_doviz_ozet", return_value={}), \
                patch("infra.mukayese_fetch.fetch_nakit_bakiye_gl", return_value=0.0):
            donem_kapanisi(_CFG, "2024-07-28", "2025-07-28")

        self.assertEqual(akis_pencereleri,                       # akış: iki parça
                         [("2024-07-28", "2024-12-31"), ("2025-01-01", "2025-07-28")])
        self.assertEqual(mizan_gunleri, ["2025-07-28"])          # bakiye: tek gün


class TestYardimciPencereKirpma(unittest.TestCase):
    """«Son 12 ay» / «son 90 gün» gibi referans pencereler de aralığın dışına çıkamaz."""

    def test_ogrenme_penceresi_bastan_geriye_gitmez(self) -> None:
        from domain.tahmin import ogrenme_penceresi_bas
        # 3 aylık dönem seçildi: pencere 12 aya GENİŞLETİLMEZ, seçimde kalır.
        self.assertEqual(ogrenme_penceresi_bas("2026-07-01", "2026-09-30"), "2026-07-01")

    def test_genis_donemde_son_12_ay_kullanilir(self) -> None:
        """Aralık genişse pencere yine son 12 ay: seçim dışına çıkılmıyor, kısaltılıyor."""
        from domain.tahmin import ogrenme_penceresi_bas
        self.assertEqual(ogrenme_penceresi_bas("2024-01-01", "2026-09-30"), "2025-09-30")

    def test_runway_penceresi_bastan_geriye_gitmez(self) -> None:
        from ui.tabs.nakit_akis_tab import _runway_referans_bas
        self.assertEqual(_runway_referans_bas("2026-07-01", "2026-07-28"), "2026-07-01")
        # Aralık 90 günden genişse pencere yine 90 gün.
        self.assertEqual(_runway_referans_bas("2025-01-01", "2026-07-28"), "2026-04-30")

    def test_pencere_kirp_yardimcisi(self) -> None:
        from infra.mukayese_fetch import pencere_kirp
        self.assertEqual(pencere_kirp("2026-01-01", "2026-07-28", "2025-08-01"), "2026-01-01")
        self.assertEqual(pencere_kirp("2025-01-01", "2026-07-28", "2025-08-01"), "2025-08-01")


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
