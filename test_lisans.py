"""
Premium sekme kilidi — bölünme, karar mantığı ve «şüphede kalınca aç» kuralı.

Bu testlerin çoğu saftır (Windows gerekmez): karar `domain/lisans.py`de, Store'a
sormak `infra/store_lisans.py`nin işi. Ayrım bilerek böyle — kilit kuralı, WinRT
olmayan bir makinede de sınanabilmeli.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from domain.lisans import (
    PREMIUM_SEKMELER,
    UCRETSIZ_SEKMELER,
    LisansDurumu,
    premium_acik,
    premium_isaretli,
    sekme_kilitli,
)

_KOK = Path(__file__).parent


def _sekme_basliklari() -> set[str]:
    adlar = set()
    for yol in (_KOK / "ui" / "tabs").glob("*_tab.py"):
        m = re.search(r'BASLIK\s*=\s*"([^"]+)"', yol.read_text(encoding="utf-8"))
        if m:
            adlar.add(m.group(1))
    return adlar


class TestBolunme(unittest.TestCase):
    """
    Her sekme İKİ listeden BİRİNDE olmalı.

    `sekme_kilitli` listelenmemiş sekmeyi ücretsiz sayıyor (şüphede kalınca aç). Bu
    emniyet supabı, kural değil: yeni bir sekme eklenip listeye yazılmazsa sessizce
    bedava dağıtılırdı. Bekçi burada.
    """

    def test_her_sekme_tam_olarak_bir_listede(self) -> None:
        basliklar = _sekme_basliklari()
        self.assertEqual(len(basliklar), 9, "sekme sayısı değişmiş — bölünme gözden geçirilmeli")
        listelenen = UCRETSIZ_SEKMELER | PREMIUM_SEKMELER
        self.assertEqual(
            basliklar - listelenen, set(),
            "Bu sekmeler ne ücretsiz ne premium listesinde — sessizce bedava dağıtılır")
        self.assertEqual(
            listelenen - basliklar, set(),
            "Listede gerçek bir sekmeye karşılık gelmeyen ad var (yazım hatası?)")
        self.assertEqual(
            UCRETSIZ_SEKMELER & PREMIUM_SEKMELER, set(),
            "Bir sekme hem ücretsiz hem premium listesinde")

    def test_resmi_tablolar_ucretsiz(self) -> None:
        """Müşavirin zaten ürettiği tablolara para istemek ürünü ucuzlatır."""
        self.assertIn("Bilanço", UCRETSIZ_SEKMELER)
        self.assertIn("Gelir Tablosu", UCRETSIZ_SEKMELER)

    def test_yapay_zeka_premium(self) -> None:
        self.assertIn("Yapay Zekâ Yorumu", PREMIUM_SEKMELER)


class TestKarar(unittest.TestCase):
    def test_sahip_ise_acik(self) -> None:
        self.assertTrue(premium_acik(LisansDurumu.SAHIP, onbellek=False))

    def test_okunamazsa_onbellek_belirler(self) -> None:
        """Çevrimdışı ya da Windows dışı: en son bilinen durum korunur."""
        self.assertTrue(premium_acik(LisansDurumu.BILINMIYOR, onbellek=True))
        self.assertFalse(premium_acik(LisansDurumu.BILINMIYOR, onbellek=False))

    def test_olumsuz_cevap_odemis_musteriyi_kilitlemez(self) -> None:
        """
        `YOK` KESİN DEĞİLDİR: Microsoft hesabına giriş yapmamış ya da lisansı henüz
        senkronlanmamış kullanıcıda da dönüyor. Otomatik kilitlemek, tam da
        engellemeye çalıştığımız hatayı üretirdi — hele yama takvimi yokken.
        """
        self.assertTrue(premium_acik(LisansDurumu.YOK, onbellek=True))

    def test_hic_dogrulanmamissa_ucretsiz(self) -> None:
        self.assertFalse(premium_acik(LisansDurumu.YOK, onbellek=False))


class TestKilitVeEtiket(unittest.TestCase):
    def test_premium_kapaliyken_yalniz_premium_sekmeler_kilitli(self) -> None:
        for ad in PREMIUM_SEKMELER:
            with self.subTest(sekme=ad):
                self.assertTrue(sekme_kilitli(ad, premium_acik_mi=False))
        for ad in UCRETSIZ_SEKMELER:
            with self.subTest(sekme=ad):
                self.assertFalse(sekme_kilitli(ad, premium_acik_mi=False))

    def test_premium_acikken_hicbiri_kilitli_degil(self) -> None:
        for ad in PREMIUM_SEKMELER | UCRETSIZ_SEKMELER:
            with self.subTest(sekme=ad):
                self.assertFalse(sekme_kilitli(ad, premium_acik_mi=True))

    def test_isaret_satin_alinca_kalkar(self) -> None:
        """Ödemiş kullanıcıya hâlâ kilit rozeti göstermek kabul edilemez."""
        self.assertTrue(premium_isaretli("Yapay Zekâ Yorumu", premium_acik_mi=False))
        self.assertFalse(premium_isaretli("Yapay Zekâ Yorumu", premium_acik_mi=True))

    def test_ucretsiz_sekmede_isaret_yok(self) -> None:
        self.assertFalse(premium_isaretli("Nakit Akış", premium_acik_mi=False))


class TestStoreKoprusu(unittest.TestCase):
    """Lisans okuyucu HİÇBİR koşulda uygulamayı düşürmez."""

    def test_lisans_okuma_hicbir_kosulda_dusurmez(self) -> None:
        """
        Köprü istisna ATMAZ; her platformda geçerli bir durum döner.

        BU TEST DÜZELTİLDİ: eskiden her yerde `BILINMIYOR` bekliyordu, çünkü
        `winsdk` hiç paketlenmemişti ve import daima hata veriyordu. Bağımlılık
        eklenince Windows'ta köprü GERÇEKTEN çalıştı ve «bu hesapta eklenti yok»
        anlamında `YOK` döndü — yani testi kıran şey, düzelen davranıştı.
        Windows dışında hâlâ `BILINMIYOR` olmalı: sorulacak bir Store yok.
        """
        import sys

        from infra.store_lisans import lisans_durumu

        sonuc = lisans_durumu()
        self.assertIsInstance(sonuc, LisansDurumu)
        if sys.platform != "win32":
            self.assertIs(sonuc, LisansDurumu.BILINMIYOR)

    def test_satin_alma_pencereye_baglanmadan_denenmez(self) -> None:
        """
        BU BEKÇİ TERSİNE ÇEVRİLDİ — silinmedi, tarihi burada duruyor.

        Eskiden «`request_purchase_async` ÇAĞRILMIYOR» diye sınıyordu: satın alma
        Store'un ürün sayfasında tamamlanacaktı. ÖLÇÜM o kararı çürüttü — yayındaki,
        eksiksiz yapılandırılmış bir eklenti için bile `apps.microsoft.com/detail/
        9PF68PSTZNTP` 404/ProductNotFound döner; eklentilerin web sayfası yoktur.
        Uygulama içi satın alma tek yol oldu.

        Yeni koşul: satın alma çağrısı VAR ve HWND bağlaması olmadan yapılmıyor.
        Bağlanmamış çağrı sessizce başarısız olur ya da arayüzü dondurur.
        """
        import ast

        kaynak = (_KOK / "infra" / "store_lisans.py").read_text(encoding="utf-8")
        agac = ast.parse(kaynak)
        cagrilar = {d.attr for d in ast.walk(agac) if isinstance(d, ast.Attribute)}
        self.assertIn("request_purchase_async", cagrilar,
                      "satın alma yolu yok — eklenti hiç satılamaz")

        govde = {f.name: f for f in ast.walk(agac) if isinstance(f, ast.FunctionDef)}
        self.assertIn("_pencereye_bagla", govde, "HWND bağlama adımı yok")
        satin_al = govde.get("satin_al")
        self.assertIsNotNone(satin_al)
        cagrilanlar = {c.func.id for c in ast.walk(satin_al)
                       if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        self.assertIn("_pencereye_bagla", cagrilanlar,
                      "satın alma pencereye bağlanmadan çağrılıyor")

    def test_lisans_okuma_zaman_asimina_bagli(self) -> None:
        """
        WinRT asılabilir ve bu çağrılar UI thread'inden yapılıyor. Zaman aşımı
        olmadan Store'un takılması uygulamayı kilitler.
        """
        import ast

        kaynak = (_KOK / "infra" / "store_lisans.py").read_text(encoding="utf-8")
        adlar = {d.attr for d in ast.walk(ast.parse(kaynak))
                 if isinstance(d, ast.Attribute)}
        self.assertIn("wait_for", adlar, "WinRT çağrısı zaman aşımısız")

    def test_magaza_url_store_id_ile_kurulu(self) -> None:
        from infra.surum import MAGAZA_STORE_ID, MAGAZA_URL
        self.assertEqual(MAGAZA_STORE_ID, "9NB421K1Z0GB")
        self.assertIn(MAGAZA_STORE_ID, MAGAZA_URL)
        self.assertTrue(MAGAZA_URL.startswith("ms-windows-store://"))

    def test_eklentinin_web_sayfasina_gonderilmiyor(self) -> None:
        """
        `satin_alma_url()` SİLİNDİ — eklentinin web sayfası yok (404 ölçüldü).

        Fonksiyon dursaydı biri altı ay sonra «hazır duruyor» deyip 404'e geri
        dönerdi. `magaza_sayfasi_ac()` artık UYGULAMANIN sayfasını açıyor ve tek
        işi «Store sürümünü kur» demek.
        """
        import infra.surum as surum

        self.assertFalse(hasattr(surum, "satin_alma_url"),
                         "ölü fonksiyon duruyor — 404'e geri dönüş daveti")
        self.assertFalse(hasattr(surum, "eklenti_tanimli"))

        import ast
        kaynak = (_KOK / "infra" / "store_lisans.py").read_text(encoding="utf-8")
        govde = {f.name: f for f in ast.walk(ast.parse(kaynak))
                 if isinstance(f, ast.FunctionDef)}
        adlar = {d.id for d in ast.walk(govde["magaza_sayfasi_ac"])
                 if isinstance(d, ast.Name)}
        self.assertIn("MAGAZA_URL", adlar)
        self.assertNotIn("PREMIUM_ADDON_STORE_ID", adlar,
                         "eklentinin sayfasına gönderiliyor — o sayfa 404")

    def test_iki_kimlik_karistirilmamis(self) -> None:
        """
        Lisans eşleşmesi ÜRÜN KİMLİĞİNE, satın alma linki STORE ID'ye bakar.
        İkisini karıştırmak sessiz arıza: kullanıcı öder, premium açılmaz.
        """
        import ast

        from infra.surum import PREMIUM_ADDON_STORE_ID, PREMIUM_ADDON_URUN_ID

        self.assertEqual(PREMIUM_ADDON_URUN_ID, "mikrapor-premium")
        self.assertEqual(PREMIUM_ADDON_STORE_ID, "9PF68PSTZNTP")
        self.assertNotEqual(PREMIUM_ADDON_URUN_ID, PREMIUM_ADDON_STORE_ID)
        # LİSANS OKUMA ürün kimliğine bakar; SATIN ALMA Store ID'ye. İkisi de aynı
        # dosyada ama ayrı fonksiyonlarda — hangisinin nerede olduğu sınanır.
        kaynak = (_KOK / "infra" / "store_lisans.py").read_text(encoding="utf-8")
        govde = {f.name: f for f in ast.walk(ast.parse(kaynak))
                 if isinstance(f, ast.FunctionDef)}
        okuma = {d.id for d in ast.walk(govde["lisans_durumu"]) if isinstance(d, ast.Name)}
        self.assertIn("PREMIUM_ADDON_URUN_ID", okuma)
        self.assertNotIn("PREMIUM_ADDON_STORE_ID", okuma,
                         "lisans eşleşmesinde Store ID kullanılmış — hiç eşleşmez")
        alma = {d.id for d in ast.walk(govde["satin_al"]) if isinstance(d, ast.Name)}
        self.assertIn("PREMIUM_ADDON_STORE_ID", alma)


try:
    from PyQt6.QtWidgets import QApplication
    _PYQT = True
except ImportError:
    _PYQT = False


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestKilitliSekmeEkrani(unittest.TestCase):
    """Kilitli sekme AÇILIR ve ne kaçırıldığını anlatır; uydurma rakam göstermez."""

    @classmethod
    def setUpClass(cls) -> None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _sekme(self, cls, lisansli: bool):
        from unittest.mock import patch

        import ui.premium as premium
        from ui.donem import DonemDurumu

        premium.sifirla()
        with patch("infra.config.premium_onbellek", return_value=lisansli):
            return cls(DonemDurumu())

    def _cta(self, sekme) -> str:
        from ui.empty_state import _EmptyCtaButton
        dugmeler = sekme._empty.findChildren(_EmptyCtaButton)
        return dugmeler[0]._label if dugmeler else ""

    def test_kilitli_sekmede_cta_premium(self) -> None:
        from ui.premium import PREMIUM_CTA
        from ui.tabs.ai_yorum_tab import AiYorumTab

        sekme = self._sekme(AiYorumTab, lisansli=False)
        self.assertTrue(sekme.kilitli())
        self.assertEqual(self._cta(sekme), PREMIUM_CTA)

    def test_lisansliyken_normal_cta(self) -> None:
        from ui.tabs.ai_yorum_tab import AiYorumTab

        sekme = self._sekme(AiYorumTab, lisansli=True)
        self.assertFalse(sekme.kilitli())
        self.assertNotEqual(self._cta(sekme), "")
        self.assertNotIn("Premium", self._cta(sekme))

    def test_ucretsiz_sekme_hic_kilitlenmez(self) -> None:
        """Sekiz rapor lisanssız da tam çalışır — ekranda hiçbir şey eksilmez."""
        from ui.tabs.nakit_akis_tab import NakitAkisTab
        from ui.tabs.reel_deger_tab import ReelDegerTab

        for cls in (NakitAkisTab, ReelDegerTab):
            with self.subTest(sekme=cls.BASLIK):
                self.assertFalse(self._sekme(cls, lisansli=False).kilitli())

    def test_kendi_build_yazan_sekme_de_calisir(self) -> None:
        """
        Tahmin kendi `_build`'ini yazıyor ve boş ekranı ayrı kuruyordu — `premium_tazele`
        orada AttributeError veriyordu. Sekme artık ücretsiz ama yol hâlâ koşmalı.
        """
        from ui.tabs.tahmin_tab import TahminTab

        sekme = self._sekme(TahminTab, lisansli=False)
        self.assertFalse(sekme.kilitli())
        sekme.premium_tazele()  # patlamamalı

    def test_kilitli_sekmede_getir_sorgu_baslatmaz(self) -> None:
        """
        Chrome toolbar'daki «Raporu Getir» de `_on_getir`'e geliyor; ekrandaki düğmeyi
        değiştirmek tek başına koruma değil.
        """
        from unittest.mock import patch

        from ui.tabs.ai_yorum_tab import AiYorumTab

        sekme = self._sekme(AiYorumTab, lisansli=False)
        with patch.object(sekme, "_ayarlar_tamam") as ayarlar, \
             patch.object(sekme, "_on_premium") as premium_cagrisi:
            sekme._on_getir()
        ayarlar.assert_not_called()
        premium_cagrisi.assert_called_once()


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestCiktiKilidi(unittest.TestCase):
    """
    PDF/CSV premium — ASIL KİLİT BURADA.

    Sekme kilidi tek sekmeye indi; gelir modelinin taşıyıcısı dışa aktarma oldu.
    Kapı tek: `RaporTab.disa_aktar`. `_on_pdf` alt sınıflarda eziliyor, kilidi oraya
    koymak dokuz sekmede dokuz kez yazmak demekti — biri unutulunca sessizce bedava.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def _sekme(self, cls, lisansli: bool):
        return TestKilitliSekmeEkrani._sekme(self, cls, lisansli)

    def test_karar_saf_fonksiyonda(self) -> None:
        from domain.lisans import disa_aktarim_kilitli

        self.assertTrue(disa_aktarim_kilitli(premium_acik_mi=False))
        self.assertFalse(disa_aktarim_kilitli(premium_acik_mi=True))

    def test_ucretsiz_sekmeden_de_pdf_alinamaz(self) -> None:
        """Sekme ücretsiz olsa bile ÇIKTI kilitli — kilit sekmeye değil çıktıya bağlı."""
        from unittest.mock import patch

        from ui.tabs.nakit_akis_tab import NakitAkisTab

        sekme = self._sekme(NakitAkisTab, lisansli=False)
        self.assertFalse(sekme.kilitli())
        with patch.object(sekme, "_on_pdf") as pdf, \
             patch.object(sekme, "_on_premium") as premium_cagrisi:
            sekme.disa_aktar("pdf")
        pdf.assert_not_called()
        premium_cagrisi.assert_called_once()

    def test_csv_de_ayni_kapidan_gecer(self) -> None:
        from unittest.mock import patch

        from ui.tabs.nakit_akis_tab import NakitAkisTab

        sekme = self._sekme(NakitAkisTab, lisansli=False)
        with patch.object(sekme, "_on_csv") as csv, \
             patch.object(sekme, "_on_premium") as premium_cagrisi:
            sekme.disa_aktar("csv")
        csv.assert_not_called()
        premium_cagrisi.assert_called_once()

    def test_lisansliyken_cikti_gecer(self) -> None:
        from unittest.mock import patch

        from ui.tabs.nakit_akis_tab import NakitAkisTab

        sekme = self._sekme(NakitAkisTab, lisansli=True)
        with patch.object(sekme, "_on_pdf") as pdf:
            sekme.disa_aktar("pdf")
        pdf.assert_called_once()

    def test_chrome_disa_aktar_kapisindan_gecer(self) -> None:
        """
        Toolbar `_on_pdf`i DOĞRUDAN çağırmamalı; çağırırsa kilit büsbütün baypas olur.
        """
        import ast
        import inspect

        import ui.app as app_mod

        agac = ast.parse(inspect.getsource(app_mod))
        cagrilar = {
            n.func.attr for n in ast.walk(agac)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        self.assertIn("disa_aktar", cagrilar)
        self.assertNotIn("_on_pdf", cagrilar)
        self.assertNotIn("_on_csv", cagrilar)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestGetirKapisiMuhurlu(unittest.TestCase):
    """
    `_on_getir` alt sınıflarda EZİLMEZ — premium kilidi orada.

    Gerçek arıza: Yapay Zekâ sekmesi eziyordu ve kendi ön koşullarını `super()`den
    ÖNCE koşturuyordu. Kilitli kullanıcı «Raporu Getir»e basınca premium penceresi
    değil «yapay zekâ ayarları eksik» uyarısı alıyordu; tek premium sekmenin kilidi
    büsbütün baypas oluyordu. Ön koşul artık `_getir_on_kosul`a yazılır.
    """

    def test_hicbir_sekme_on_getiri_ezmiyor(self) -> None:
        import ast
        import pathlib

        kok = pathlib.Path(__file__).resolve().parent / "ui" / "tabs"
        ezenler = []
        for yol in sorted(kok.glob("*_tab.py")):
            agac = ast.parse(yol.read_text(encoding="utf-8"))
            for d in ast.walk(agac):
                if isinstance(d, ast.FunctionDef) and d.name == "_on_getir":
                    ezenler.append(yol.name)
        self.assertEqual(ezenler, [],
                         "premium kilidi baypas olur — ön koşulu _getir_on_kosul'a yazın")


class TestSatinAlmaSonucu(unittest.TestCase):
    """
    Satın alma dallarının tamamı — Store OLMADAN sınanır.

    CI'da Windows Store yok; gerçek satın alma denenemez. Ama enum eşlemesi ve
    kararlar saf katmanda olduğu için burada tam kapsanır. Son metre (gerçek
    hesapla ödeme) yalnız ELLE doğrulanabilir; bu testler onun yerine geçmez.
    """

    def test_her_dal_bir_mesaj_uretiyor(self) -> None:
        from domain.lisans import SatinAlmaSonucu, satin_alma_mesaji

        for sonuc in SatinAlmaSonucu:
            with self.subTest(sonuc=sonuc):
                baslik, govde = satin_alma_mesaji(sonuc)
                self.assertTrue(baslik.strip())
                self.assertTrue(govde.strip())

    def test_yalniz_alindi_ve_zaten_var_acar(self) -> None:
        from domain.lisans import SatinAlmaSonucu as S
        from domain.lisans import premium_acildi_mi

        self.assertTrue(premium_acildi_mi(S.ALINDI))
        self.assertTrue(premium_acildi_mi(S.ZATEN_VAR))
        for sonuc in (S.TAMAMLANMADI, S.AG_HATASI, S.SUNUCU_HATASI,
                      S.BASLATILAMADI, S.PENCERE_ACILMADI, S.YANIT_YOK):
            with self.subTest(sonuc=sonuc):
                self.assertFalse(premium_acildi_mi(sonuc))

    def test_baslatilamadi_ile_yanit_yok_ayri_mesaj(self) -> None:
        """
        CANLIDA YAŞANDI: Store'un satın alma penceresi AÇILDI, kullanıcı ödeme
        yaparken bizim 20 sn'lik zaman aşımımız bekleyişi iptal etti, pencere yok
        oldu ve ekrana «yalnız Store'dan kurulan sürümde satın alınabilir» yazdık —
        kullanıcı zaten Store sürümündeydi. Yanlış şeyi suçlayan mesaj, hiç mesaj
        vermemekten kötüdür.
        """
        from domain.lisans import SatinAlmaSonucu as S
        from domain.lisans import satin_alma_mesaji

        b_baslik, b_govde = satin_alma_mesaji(S.BASLATILAMADI)
        y_baslik, y_govde = satin_alma_mesaji(S.YANIT_YOK)
        self.assertNotEqual(b_baslik, y_baslik)
        # «Başladı ama cevap gelmedi» durumunda kurulum biçimi SUÇLANMAZ.
        self.assertNotIn("kurulan", y_govde)
        self.assertIn("kurulan", b_govde)

    def test_store_sayfasi_yalniz_store_disi_kurulumda_acilir(self) -> None:
        """
        Store SÜRÜMÜNDE uygulamanın sayfası «Aç» gösterir, satın alma düğmesi yoktur
        (canlıda görüldü). Oraya yönlendirmek kullanıcıyı çıkmaza sokar; yalnız
        StoreContext hiç kurulamadığında — yani Store'dan kurulmamış sürümde — gidilir.
        """
        import ast
        import inspect

        import ui.rapor_tab as mod

        govde = {f.name: f for f in ast.walk(ast.parse(inspect.getsource(mod)))
                 if isinstance(f, ast.FunctionDef)}
        kaynak = ast.unparse(govde["_on_premium"])
        self.assertIn("BASLATILAMADI", kaynak)
        self.assertIn("magaza_sayfasi_ac", kaynak)
        # Zaman aşımı / pencere hatası dallarında sayfa AÇILMAZ.
        for kotu in ("YANIT_YOK", "PENCERE_ACILMADI"):
            self.assertNotIn(f"{kotu}:\n", kaynak)

    def test_satin_alma_zaman_asimi_insan_hizinda(self) -> None:
        """
        Lisans okuma sınırı satın almaya UYGULANAMAZ: biri makine, diğeri insan
        hızında. Aynı sabiti paylaşmak kullanıcının elinden ödeme penceresini aldı.
        """
        from infra.store_lisans import _SATIN_ALMA_ASIMI, _ZAMAN_ASIMI

        self.assertGreater(_SATIN_ALMA_ASIMI, 300,
                           "satın alma sınırı insan işlemi için çok kısa")
        self.assertLess(_ZAMAN_ASIMI, 60, "lisans okuma sınırı gereksiz uzun")

    def test_tamamlanmadi_mesaji_suclamiyor(self) -> None:
        """
        `NotPurchased` hem vazgeçmede hem ödeme reddinde dönüyor. «İptal ettiniz»
        demek, kartı reddedilen kullanıcıya yanlış sebep söylemektir.
        """
        from domain.lisans import SatinAlmaSonucu, satin_alma_mesaji

        _, govde = satin_alma_mesaji(SatinAlmaSonucu.TAMAMLANMADI)
        for sozcuk in ("iptal", "vazgeç", "reddedil"):
            self.assertNotIn(sozcuk, govde.lower(), f"sebep uyduruluyor: {sozcuk}")
        self.assertIn("ücret alınmadı", govde.lower())

    def test_winrt_kodlari_dogru_esleniyor(self) -> None:
        """StorePurchaseStatus sayı değerleri WinRT'de sabittir."""
        from domain.lisans import SatinAlmaSonucu as S
        from infra.store_lisans import _durum_esle

        class _Sahte:
            def __init__(self, kod): self.status = kod

        beklenen = {0: S.ALINDI, 1: S.ZATEN_VAR, 2: S.TAMAMLANMADI,
                    3: S.AG_HATASI, 4: S.SUNUCU_HATASI}
        for kod, bekle in beklenen.items():
            with self.subTest(kod=kod):
                self.assertIs(_durum_esle(_Sahte(kod)), bekle)
        self.assertIs(_durum_esle(None), S.YANIT_YOK)
        self.assertIs(_durum_esle(_Sahte(99)), S.YANIT_YOK)

    @unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
    def test_satin_alma_sonrasi_lisans_yeniden_okunmuyor(self) -> None:
        """
        EN KRİTİK DAL: `ALINDI` geldiğinde premium DOĞRUDAN açılır.

        Lisans dağıtımı satın almadan hemen sonra oturmamış olabilir; oraya sorup
        «yok» cevabı alınsa kullanıcı ödemiş ve ekran kilitli kalmış olurdu.
        """
        import ast
        import inspect

        import ui.rapor_tab as mod

        kaynak = inspect.getsource(mod)
        govde = {f.name: f for f in ast.walk(ast.parse(kaynak))
                 if isinstance(f, ast.FunctionDef)}
        cagrilar = {c.func.id for c in ast.walk(govde["_on_premium"])
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        self.assertIn("premium_ac", cagrilar, "satın alma sonrası premium açılmıyor")
        self.assertNotIn("premium_durumu", cagrilar,
                         "satın alma sonrası lisans yeniden okunuyor — ödeyen kilitli kalır")

    def test_premium_ac_onbellege_yaziyor(self) -> None:
        """Açılan kilit yeniden başlatınca kapanmamalı."""
        import ast
        import inspect

        import ui.premium as mod

        govde = {f.name: f for f in ast.walk(ast.parse(inspect.getsource(mod)))
                 if isinstance(f, ast.FunctionDef)}
        cagrilar = {c.func.id for c in ast.walk(govde["premium_ac"])
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        self.assertIn("premium_onbellek_yaz", cagrilar)


class TestAcilisYolu(unittest.TestCase):
    """Lisans okuması açılış yolundan ÇIKARILDI — Store yavaşsa uygulama donmasın."""

    def test_varsayilan_cagri_aga_cikmiyor(self) -> None:
        import ast
        import inspect

        import ui.premium as mod

        govde = {f.name: f for f in ast.walk(ast.parse(inspect.getsource(mod)))
                 if isinstance(f, ast.FunctionDef)}
        kaynak = ast.unparse(govde["premium_durumu"])
        # `lisans_durumu` importu YALNIZ yenile=True dalında olmalı.
        self.assertIn("if not yenile", kaynak,
                      "ağa çıkmayan hızlı yol yok — açılışta Store'a soruluyor")

    @unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
    def test_lisans_arkaplanda_okunuyor(self) -> None:
        import ast
        import inspect

        import ui.app as mod

        kaynak = inspect.getsource(mod)
        self.assertIn("_lisansi_arkaplanda_oku", kaynak)
        govde = {f.name: f for f in ast.walk(ast.parse(kaynak))
                 if isinstance(f, ast.FunctionDef)}
        self.assertIn("_lisansi_arkaplanda_oku", govde)
