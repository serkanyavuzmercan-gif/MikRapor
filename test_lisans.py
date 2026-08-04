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
        self.assertTrue(premium_isaretli("Reel Değer", premium_acik_mi=False))
        self.assertFalse(premium_isaretli("Reel Değer", premium_acik_mi=True))

    def test_ucretsiz_sekmede_isaret_yok(self) -> None:
        self.assertFalse(premium_isaretli("Nakit Akış", premium_acik_mi=False))


class TestStoreKoprusu(unittest.TestCase):
    """Lisans okuyucu HİÇBİR koşulda uygulamayı düşürmez."""

    def test_windows_disinda_bilinmiyor_doner(self) -> None:
        from infra.store_lisans import lisans_durumu
        self.assertIs(lisans_durumu(), LisansDurumu.BILINMIYOR)

    def test_uygulama_ici_odeme_penceresi_yazilmadi(self) -> None:
        """
        `RequestPurchaseAsync` + HWND/COM bağlama yolu bilerek KULLANILMIYOR: Python'dan
        kırılgan ve bozulursa sonuç «kimse ödeme yapamıyor» olur. Satın alma Store
        sayfasında tamamlanır.

        Metin araması YETMEZ: modülün docstring'i tam olarak bu yolu NEDEN
        kullanmadığımızı anlatıyor ve kendi bekçisini kırmızıya düşürüyordu. AST'den
        yalnız gerçek çağrılara bakılır.
        """
        import ast

        agac = ast.parse((_KOK / "infra" / "store_lisans.py").read_text(encoding="utf-8"))
        yasak = {"request_purchase_async", "requestpurchaseasync",
                 "iinitializewithwindow", "queryinterface"}
        bulunan = [d.attr for d in ast.walk(agac)
                   if isinstance(d, ast.Attribute) and d.attr.lower() in yasak]
        self.assertEqual(bulunan, [], f"uygulama içi ödeme yolu yazılmış: {bulunan}")

    def test_magaza_url_store_id_ile_kurulu(self) -> None:
        from infra.surum import MAGAZA_STORE_ID, MAGAZA_URL
        self.assertEqual(MAGAZA_STORE_ID, "9NB421K1Z0GB")
        self.assertIn(MAGAZA_STORE_ID, MAGAZA_URL)
        self.assertTrue(MAGAZA_URL.startswith("ms-windows-store://"))

    def test_satin_alma_eklentinin_sayfasina_gider(self) -> None:
        """
        Uygulamanın sayfasında «Yüklü / Aç» yazar — satın alma düğmesi EKLENTİNİN
        kendi sayfasındadır. Kimlik yazılmadan kullanıcı premium'u nereden alacağını
        bulamaz; kimlik yazılınca link oraya gitmek ZORUNDA.
        """
        from unittest.mock import patch

        import infra.surum as surum

        with patch.object(surum, "PREMIUM_ADDON_STORE_ID", "9XYZTESTADDON"):
            self.assertIn("9XYZTESTADDON", surum.satin_alma_url())
            self.assertTrue(surum.eklenti_tanimli())
        # Kimlik yokken uygulamanın sayfasına düşülür (eksik ama kırık değil).
        with patch.object(surum, "PREMIUM_ADDON_STORE_ID", ""):
            self.assertEqual(surum.satin_alma_url(), surum.MAGAZA_URL)
            self.assertFalse(surum.eklenti_tanimli())


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
        from ui.tabs.reel_deger_tab import ReelDegerTab

        sekme = self._sekme(ReelDegerTab, lisansli=False)
        self.assertTrue(sekme.kilitli())
        self.assertEqual(self._cta(sekme), PREMIUM_CTA)

    def test_lisansliyken_normal_cta(self) -> None:
        from ui.tabs.reel_deger_tab import ReelDegerTab

        sekme = self._sekme(ReelDegerTab, lisansli=True)
        self.assertFalse(sekme.kilitli())
        self.assertNotEqual(self._cta(sekme), "")
        self.assertNotIn("Premium", self._cta(sekme))

    def test_ucretsiz_sekme_hic_kilitlenmez(self) -> None:
        from ui.tabs.nakit_akis_tab import NakitAkisTab

        self.assertFalse(self._sekme(NakitAkisTab, lisansli=False).kilitli())

    def test_kendi_build_yazan_sekme_de_kilitleniyor(self) -> None:
        """
        Tahmin kendi `_build`'ini yazıyor ve boş ekranı ayrı kuruyordu — kilit orada
        atlanıyor, üstelik `premium_tazele` AttributeError veriyordu.
        """
        from ui.premium import PREMIUM_CTA
        from ui.tabs.tahmin_tab import TahminTab

        sekme = self._sekme(TahminTab, lisansli=False)
        self.assertTrue(sekme.kilitli())
        self.assertEqual(self._cta(sekme), PREMIUM_CTA)
        sekme.premium_tazele()  # patlamamalı

    def test_kilitli_sekmede_getir_sorgu_baslatmaz(self) -> None:
        """
        Chrome toolbar'daki «Raporu Getir» de `_on_getir`'e geliyor; ekrandaki düğmeyi
        değiştirmek tek başına koruma değil.
        """
        from unittest.mock import patch

        from ui.tabs.reel_deger_tab import ReelDegerTab

        sekme = self._sekme(ReelDegerTab, lisansli=False)
        with patch.object(sekme, "_ayarlar_tamam") as ayarlar, \
             patch.object(sekme, "_on_premium") as premium_cagrisi:
            sekme._on_getir()
        ayarlar.assert_not_called()
        premium_cagrisi.assert_called_once()


if __name__ == "__main__":
    unittest.main()
