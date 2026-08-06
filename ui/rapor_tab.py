"""
Ortak rapor sekmesi iskeleti (RaporTab) + arka plan çalıştırma.

Design A: dönem/Getir/PDF/CSV üst chrome toolbar'dadır (ui.chrome_toolbar).
Bu sınıf içerik + empty state + worker yönetir; chrome app.py üzerinden bağlanır.

Chrome paylaşımlı olduğu için yalnız aktif sekme (chrome.aktif_tab) buton/status günceller;
arka planda biten işler yalnızca kendi içerik alanını doldurur.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from infra.config import MikroConfig, load_config
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import fetch_firma_adi
from ui.bilesenler import csv_kaydet, hos_geldin, rapor_slug
from ui.chrome_toolbar import ChromeToolbar
from ui.donem import DonemDurumu
from ui.empty_state import DEFAULT_HERO_ASSET, HERO_SOLUK_OPACITY, build_soluk_arka_plan
from ui.mikro_settings_dialog import MikroAyarlarDialog
from ui.premium import PREMIUM_CTA, premium_durumu
from ui.styles import PAGE_BG
from ui.worker import IsFonksiyonu, RaporWorker
from ui.yukleniyor import YukleniyorEkrani

# Mikro kurulumlarında bu yıldan eskisi pratikte yok; asıl amaç 7026 gibi
# parmak hatalarını yakalamak, geçmişi kısıtlamak değil.
YIL_ALT = 1990

# İçerik kökü yarı saydam beyaz — altındaki soluk illüstrasyon hafifçe görünsün
_PAGE_BG_SOLUK = "rgba(255, 255, 255, 0.72)"


def firma_getir(cfg: MikroConfig, client: MikroClient) -> str:
    """Firma ünvanı: elle girilmişse o; boşsa Mikro'dan. (Worker thread'inde çağrılır.)"""
    firma = (cfg.firma_adi or "").strip()
    if firma:
        return firma
    try:
        return fetch_firma_adi(client)
    except MikroAPIError:
        return ""


class RaporTab(QWidget):
    """Tüm rapor sekmelerinin ortak iskeleti — bkz. modül docstring'i."""

    EMOJI = "📊"
    BASLIK = ""
    ACIKLAMA = ""
    IPUCU = ""
    GETIR_ETIKET = "Getir"
    # True ise düğmede GETIR_ETIKET yazar (tek tip «Raporu Getir» yerine).
    GETIR_ETIKET_ZORLA = False
    BASLARKEN = "Veriler çekiliyor…"
    # Yükleniyor ekranının süre ipucu; uzun süren sekmeler (yapay zekâ) bunu ezer.
    SURE_IPUCU = ""
    DONEM_ETIKET = "Dönem:"
    TEK_TARIH = False
    TARIH_GENISLIK = 130
    PDF_DESTEK = False
    EKSTRA_ETIKET = ""  # doluysa chrome'da ekstra buton (ör. Ayarlar)
    # Sekmeye özel empty/soluk görsel (assets/<ad>). Boşsa DEFAULT_HERO_ASSET.
    # Konum, cover, solukluk tüm sekmelerde ortaktır — yalnız pixmap değişir.
    HERO_ASSET = ""
    # "cover" (varsayılan) | "contain" (Trend gibi taşan görselleri sığdır)
    HERO_FIT = "cover"

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._worker: RaporWorker | None = None
        self._firma: str = ""
        self._chrome: ChromeToolbar | None = None
        self._status: QLabel | None = None
        self._rapor_var = False
        self._build()

    def bagla_chrome(self, chrome: ChromeToolbar) -> None:
        """Üst chrome toolbar'a bağlanır (aktif sekme olduğunda çağrılır)."""
        self._chrome = chrome
        chrome.set_aktif_tab(self)
        self._status = chrome.status_label()
        chrome.set_tek_tarih(self.TEK_TARIH)
        chrome.set_getir_etiket(self.GETIR_ETIKET, zorla=self.GETIR_ETIKET_ZORLA)
        chrome.set_pdf_gorunur(self.PDF_DESTEK)
        chrome.set_ekstra_gorunur(bool(self.EKSTRA_ETIKET), self.EKSTRA_ETIKET or "Hesaplama")
        # Aktif sekmenin durumunu yansıt
        if self._rapor_acik():
            chrome.set_csv_aktif(True)
            chrome.set_pdf_aktif(self.PDF_DESTEK)
        else:
            chrome.set_csv_aktif(False)
            chrome.set_pdf_aktif(False)
            chrome.set_durum_mesaj("")
        chrome.set_getir_aktif(self._worker is None)
        chrome.set_iptal_gorunur(self._worker is not None)

    # ------------------------------------------------------------------ premium
    def _bos_ekran(self) -> QWidget:
        """
        Sekme boşken görünen ekran — kilitliyken de AYNISI.

        Kullanıcı ne kaçırdığını okusun diye sekme açılıyor ve ne yaptığını anlatan
        metin (`ACIKLAMA`) gösteriliyor. Bulanık ya da uydurma rakam GÖSTERİLMEZ
        (kural 2): sahtesi kandırmak olur, gerçeğini göstermek için veriyi zaten
        çekmek gerekirdi. Değişen tek şey düğme.
        """
        # Görsel BURADA hesaplanır, __init__'te saklanmaz: Tahmin kendi `_build`'ini
        # yazıyor ve saklanan alanı hiç kurmuyordu — `premium_tazele` orada AttributeError
        # veriyordu. Tek kaynak sınıf sabitleri.
        kilit = self.kilitli()
        return hos_geldin(
            self.EMOJI,
            self.BASLIK,
            self._kilit_aciklamasi() if kilit else self.ACIKLAMA,
            self.IPUCU,
            on_cta=self._on_premium if kilit else self._on_getir,
            cta=PREMIUM_CTA if kilit else self.GETIR_ETIKET,
            hero_asset=(self.HERO_ASSET or "").strip() or DEFAULT_HERO_ASSET,
            hero_fit=(self.HERO_FIT or "cover").strip() or "cover",
        )

    def premium_tazele(self) -> None:
        """Satın alma sonrası kilit kalktıysa boş ekranı yeniden kurar."""
        yeni = self._bos_ekran()
        eski = self._empty
        self._stack.insertWidget(0, yeni)
        self._stack.removeWidget(eski)
        eski.deleteLater()
        self._empty = yeni
        if not self._rapor_var:
            self._stack.setCurrentIndex(0)

    def kilitli(self) -> bool:
        """Bu sekme premium ve lisans yoksa True. Karar `domain/lisans.py`de."""
        from domain.lisans import sekme_kilitli

        return sekme_kilitli(self.BASLIK, premium_durumu().acik)

    def _kilit_aciklamasi(self) -> str:
        """
        Sekmenin kendi ACIKLAMA'sı + neden kilitli olduğu. İkinci metin YAZILMAZ.

        Düğmenin NEREYE götürdüğü de yazar: kullanıcı Microsoft Store'a atlayınca ne
        arayacağını bilmeli, yoksa uygulamanın listelemesinde kaybolur.
        """
        return (f"{self.ACIKLAMA}<br><br>"
                "<b>Bu sekme Premium'a dâhildir.</b> Tek seferlik satın alma ile bu "
                "sekme, PDF/CSV dışa aktarma ve diğer premium özellikler kalıcı "
                "olarak açılır. Ödeme Microsoft Store penceresinde tamamlanır; "
                "MikRapor'dan çıkmanız gerekmez.")

    # Satın alma sürerken düğme yeniden tetiklenmesin — modal Store penceresi
    # açıkken Qt olay döngüsü bloke ve ikinci bir akış başlatmak kilitlenme üretir.
    _satin_aliniyor = False

    def _on_premium(self) -> None:
        """
        Premium satın alma — UYGULAMA İÇİNDE, Store penceresiyle.

        Eklentinin web sayfasına GÖNDERİLMİYOR: öyle bir sayfa yok. Yayındaki,
        eksiksiz yapılandırılmış bir add-on için bile `apps.microsoft.com/detail/
        <eklenti store id>` 404 döner (ölçüldü). Tek yol `RequestPurchaseAsync`.
        """
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QApplication

        from domain.lisans import premium_acildi_mi, satin_alma_mesaji
        from infra.store_lisans import magaza_sayfasi_ac, satin_al
        from ui.premium import premium_ac

        if RaporTab._satin_aliniyor:
            return
        RaporTab._satin_aliniyor = True
        # Store penceresi modal; Qt döngüsü o sırada bloke olacak. Meşgul imleci,
        # kullanıcıya donmadığını değil BEKLEDİĞİNİ söyler.
        QApplication.setOverrideCursor(QCursor(_Qt.CursorShape.WaitCursor))
        try:
            hwnd = int(self.window().winId())
            sonuc = satin_al(hwnd)
        finally:
            QApplication.restoreOverrideCursor()
            RaporTab._satin_aliniyor = False

        baslik, govde = satin_alma_mesaji(sonuc)
        if premium_acildi_mi(sonuc):
            premium_ac()
            pencere = self.window()
            if hasattr(pencere, "premium_hepsini_tazele"):
                pencere.premium_hepsini_tazele()
            QMessageBox.information(self, baslik, govde)
            return

        QMessageBox.information(self, baslik, govde)
        if sonuc.name == "YAPILAMADI":
            # Store'dan kurulmamış sürüm: satın alma mümkün değil. Uygulamanın
            # kendi sayfasına gönderiyoruz — orada «Al/Yükle» görecek.
            magaza_sayfasi_ac()

    def _rapor_acik(self) -> bool:
        return getattr(self, "_stack", None) is not None and self._stack.currentIndex() == 1

    def _chrome_aktif(self) -> bool:
        """Bu sekme chrome'un sahibi mi? (paylaşılan toolbar kirlenmesin)."""
        return self._chrome is not None and self._chrome.aktif_tab() is self

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._ust_alan(layout)

        # 0: empty, 1: soluk arka + rapor — tüm sekmelerde aynı motor
        self._stack = QStackedWidget()
        hero = (self.HERO_ASSET or "").strip() or DEFAULT_HERO_ASSET
        hero_fit = (self.HERO_FIT or "cover").strip() or "cover"
        self._empty = self._bos_ekran()
        self._stack.addWidget(self._empty)

        self._icerik_sayfa = QWidget()
        self._icerik_sayfa.setObjectName("raporIcerikSayfa")
        self._icerik_sayfa.setStyleSheet("QWidget#raporIcerikSayfa { background: transparent; }")
        ic_lay = QGridLayout(self._icerik_sayfa)
        ic_lay.setContentsMargins(0, 0, 0, 0)
        ic_lay.setSpacing(0)
        self._arka = build_soluk_arka_plan(
            opacity=HERO_SOLUK_OPACITY, hero_asset=hero, hero_fit=hero_fit,
        )
        ic_lay.addWidget(self._arka, 0, 0)

        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._view.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        vp = self._view.viewport()
        vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        vp.setAutoFillBackground(False)
        vp.setStyleSheet("background: transparent;")
        ic_lay.addWidget(self._view, 0, 0)
        self._view.raise_()

        self._stack.addWidget(self._icerik_sayfa)

        # 2: yükleniyor ara ekranı (fetch boyunca) — "program dondu" hissini önler
        self._yukleniyor = YukleniyorEkrani(
            hero_asset=hero, hero_fit=hero_fit, ipucu=self.SURE_IPUCU)
        self._stack.addWidget(self._yukleniyor)

        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, stretch=1)

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _ekstra_kontroller(self, controls: QHBoxLayout) -> None:
        """Geriye uyumluluk — chrome ekstra butonu kullanır."""

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        """Kontrol çubuğu ile içerik arasına widget (ör. Tahmin formu) eklemek için."""

    def _on_ekstra(self) -> None:
        """Chrome ekstra butonu (ör. Ayarlar). Alt sınıf override eder."""

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        raise NotImplementedError

    def _goster(self, sonuc: Any) -> None:
        raise NotImplementedError

    def _csv_dosya_adi(self) -> str:
        raise NotImplementedError

    @property
    def _slug(self) -> str:
        """PDF/CSV dosya adı slug'ı — sekme adından (BASLIK) türetilir; sekme adı = dosya adı."""
        return rapor_slug(self.BASLIK)

    def _csv_icerik(self) -> str | None:
        return None

    def cikti_kilitli(self) -> bool:
        """PDF/CSV premium mu? Karar tek yerde (`domain/lisans.py`)."""
        from domain.lisans import disa_aktarim_kilitli
        from ui.premium import premium_durumu

        return disa_aktarim_kilitli(premium_durumu().acik)

    def disa_aktar(self, tur: str) -> None:
        """
        PDF ve CSV'nin TEK kapısı — kilit iki ayrı yere yazılmaz.

        `_on_pdf` alt sınıflarda eziliyor; kilidi oraya koymak dokuz sekmede dokuz kez
        yazmak demekti ve biri unutulunca sessizce bedava dağıtılırdı (bkz. kural:
        aynı eleme iki yere yazılmaz).
        """
        if self.cikti_kilitli():
            self._on_premium()
            return
        if tur == "pdf":
            self._on_pdf()
        else:
            self._on_csv()

    def _on_pdf(self) -> None:
        raise NotImplementedError

    def _durum(self, mesaj: str, tur: str = "notr") -> None:
        if self._chrome_aktif() and self._chrome is not None:
            self._chrome.set_durum(mesaj, tur)

    def _icerik_koy(self, widget: QWidget) -> None:
        stil = widget.styleSheet() or ""
        if PAGE_BG in stil:
            stil = stil.replace(PAGE_BG, _PAGE_BG_SOLUK)
        else:
            stil = (stil + f"\nQWidget {{ background-color: {_PAGE_BG_SOLUK}; }}").strip()
        widget.setStyleSheet(stil)
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setAutoFillBackground(False)

        self._view.setWidget(widget)
        # Viewport her koyuşta tekrar saydam (Qt bazen sıfırlar)
        vp = self._view.viewport()
        vp.setAutoFillBackground(False)
        vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        vp.setStyleSheet("background: transparent;")

        self._arka.lower()
        self._view.raise_()
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.durdur()
        self._rapor_var = True
        self._stack.setCurrentIndex(1)

    def _ayarlar_tamam(self) -> MikroConfig | None:
        cfg = load_config()
        if cfg.is_complete():
            return cfg
        from ui.bilesenler import soru_evet_hayir
        from ui.mikro_settings_dialog import AYARLAR_ADI

        if soru_evet_hayir(
            self, f"«{AYARLAR_ADI}» Eksik",
            f"Mikro bağlantı bilgileri eksik. Üstteki «{AYARLAR_ADI}» düğmesinden "
            "doldurun.\n\nŞimdi açmak ister misiniz?",
        ):
            MikroAyarlarDialog(self).exec()
        return None

    def _yil_makul(self, tarih) -> bool:
        """
        Yıl muhasebe kaydı olabilecek bir aralıkta mı?

        Tarih kutusuna 2026 yerine 7026 yazılınca program uyarmadan kabul ediyor,
        sonra 7022-7026 yıllarını veritabanında arıyordu (canlıda görüldü). Böyle
        bir yılda kayıt olamaz; sessizce boş tablo üretmek yerine söylemek gerek.
        """
        yil = tarih.year()
        ust = date.today().year + 1        # gelecek yıla bütçe/plan girilmiş olabilir
        if YIL_ALT <= yil <= ust:
            return True
        QMessageBox.warning(
            self, "Tarih Hatası",
            f"{yil} yılı için muhasebe kaydı olamaz.\n\n"
            f"Geçerli aralık: {YIL_ALT}–{ust}. Tarihi kontrol edin.")
        return False

    def _on_getir(self) -> None:
        """
        MÜHÜRLÜ KAPI — alt sınıflar BUNU EZMEZ, `_getir_on_kosul`u yazar.

        Yapay Zekâ sekmesi bunu eziyor ve kendi ön koşullarını `super()`den ÖNCE
        çalıştırıyordu: kilitli kullanıcı «Raporu Getir»e basınca premium penceresi
        değil «yapay zekâ ayarları eksik» uyarısı alıyordu — yani tek premium
        sekmenin kilidi büsbütün baypas oluyordu. Kilit en başta, tek yerde.

        Ekrandaki düğmeyi değiştirmek de yetmez: chrome toolbar'daki «Raporu Getir»
        de buraya geliyor.
        """
        if self.kilitli():
            self._on_premium()
            return
        if not self._getir_on_kosul():
            return
        self._getir_baslat()

    def _getir_on_kosul(self) -> bool:
        """Alt sınıfın kendi ön koşulu (ayar eksik mi, onay alındı mı…). Varsayılan: yok."""
        return True

    def _getir_baslat(self) -> None:
        cfg = self._ayarlar_tamam()
        if cfg is None:
            return
        bit_d = self._donem.bit_tarih()
        if not self._yil_makul(bit_d):
            return
        if self.TEK_TARIH:
            bas = bit = bit_d.toString("yyyy-MM-dd")
        else:
            bas_d = self._donem.bas_tarih()
            if not self._yil_makul(bas_d):
                return
            if bas_d > bit_d:
                QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
                return
            bas = bas_d.toString("yyyy-MM-dd")
            bit = bit_d.toString("yyyy-MM-dd")
        self._calistir(self._is_hazirla(cfg, bas, bit))

    def _worker_birak(self, w: RaporWorker) -> None:
        """
        Çalışan worker'ı bırak — BEKLEMEDEN ve SİLMEDEN.

        KRİTİK: hâlâ çalışan bir QThread'i deleteLater ile yok etmek Qt'de
        «Destroyed while thread is still running» ile SÜRECİ ÖLDÜRÜR. Eskiden
        wait(3000) dolduktan sonra deleteLater çağrılıyordu; sunucu tarafı 3+ dakika
        süren bir sorguda İptal'e basınca program kapanıyordu (canlıda görüldü).
        Silmeyi worker'ın kendi `finished` sinyaline bağlı _on_worker_bitti yapar.
        Ayrıca wait() UI thread'ini kilitliyordu — iptal artık anında dönüyor.
        """
        w.iptal_et()
        try:
            w.bitti.disconnect(self._on_bitti)
            w.hata.disconnect(self._on_hata)
            w.ilerleme.disconnect(self._on_ilerleme)
        except TypeError:
            pass
        if w is self._worker:
            self._worker = None

    def _calistir(self, is_fn: IsFonksiyonu) -> None:
        if self._worker is not None:
            self._worker_birak(self._worker)
        if self._chrome_aktif():
            assert self._chrome is not None
            self._chrome.set_getir_aktif(False)
            self._chrome.set_iptal_gorunur(True)
        self._durum(self.BASLARKEN)
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.set_durum(self.BASLARKEN)
            self._stack.setCurrentIndex(2)
            self._yukleniyor.basla()

        worker = RaporWorker(is_fn, self)
        worker.ilerleme.connect(self._on_ilerleme)
        worker.bitti.connect(self._on_bitti)
        worker.hata.connect(self._on_hata)
        worker.finished.connect(lambda w=worker: self._on_worker_bitti(w))
        self._worker = worker
        worker.start()

    def _on_ilerleme(self, mesaj: str) -> None:
        if self.sender() is not None and self.sender() is not self._worker:
            return
        self._durum(mesaj)
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.set_durum(mesaj)

    def _on_bitti(self, sonuc: object) -> None:
        if self.sender() is not None and self.sender() is not self._worker:
            return
        if self._chrome_aktif() and self._chrome is not None:
            self._chrome.set_csv_aktif(True)
            if self.PDF_DESTEK:
                self._chrome.set_pdf_aktif(True)
            self._chrome.isaretle_son_guncelleme()
        self._goster(sonuc)

    def _on_hata(self, mesaj: str) -> None:
        if self.sender() is not None and self.sender() is not self._worker:
            return
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.durdur()
            self._stack.setCurrentIndex(1 if self._rapor_var else 0)
        self._durum("Rapor getirilemedi.", "hata")
        QMessageBox.warning(self, "Mikro Hatası", mesaj)

    def _on_worker_bitti(self, worker: RaporWorker) -> None:
        if worker is self._worker:
            self._worker = None
            if self._chrome_aktif() and self._chrome is not None:
                self._chrome.set_getir_aktif(True)
                self._chrome.set_iptal_gorunur(False)
        worker.deleteLater()

    def _on_iptal(self) -> None:
        if self._worker is not None:
            self._worker_birak(self._worker)
        if getattr(self, "_yukleniyor", None) is not None:
            self._yukleniyor.durdur()
            self._stack.setCurrentIndex(1 if self._rapor_var else 0)
        if self._chrome_aktif() and self._chrome is not None:
            self._chrome.set_getir_aktif(True)
            self._chrome.set_iptal_gorunur(False)
        self._durum("İptal edildi.", "uyari")

    def iptal_ve_bekle(self, timeout_ms: int = 8000) -> None:
        """
        Uygulama KAPANIRKEN çalışan worker'ı iptal edip bekle.

        Burada beklemek şart: süreç sonlanırken thread hâlâ koşuyorsa Qt çöker.
        Kullanıcının «İptal» düğmesi bu yolu kullanmaz — orada beklemek UI'yı kilitler.
        """
        if self._worker is None:
            return
        w = self._worker
        self._worker_birak(w)
        w.wait(timeout_ms)

    def _on_csv(self) -> None:
        icerik = self._csv_icerik()
        if icerik is None:
            return
        path = csv_kaydet(self, None, self._csv_dosya_adi(), icerik)
        if path:
            from pathlib import Path

            self._durum(f"CSV kaydedildi: {Path(path).name}", "iyi")
