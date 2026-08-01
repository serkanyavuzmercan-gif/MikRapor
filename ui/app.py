"""
MikRapor uygulama penceresi ve giriş noktası.

Design A düzeni: marka bar (sekmeler ortada) → ortak chrome toolbar → içerik.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QFont, QFontMetrics
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from infra.config import MikroConfig, load_config
from infra.mikro_api import MikroClient
from infra.surum import ALT_BASLIK, UYGULAMA_ADI
from ui.chrome_toolbar import ChromeToolbar
from ui.donem import DonemDurumu
from ui.hakkinda_dialog import HakkindaDialog
from ui.icons import icon_gear, icon_info
from ui.mikro_settings_dialog import AYARLAR_ADI, MikroAyarlarDialog
from ui.nav_tip import NavTip, bagla_nav_tip
from ui.rapor_tab import RaporTab
from ui.resources import app_icon, app_logo_pixmap
from ui.styles import APP_STYLESHEET
from ui.tabs.ai_yorum_tab import AiYorumTab
from ui.tabs.bilanco_tab import BilancoTab
from ui.tabs.gelir_tablosu_tab import GelirTablosuTab
from ui.tabs.gercek_durum_tab import GercekDurumTab
from ui.tabs.nakit_akis_tab import NakitAkisTab
from ui.tabs.reel_deger_tab import ReelDegerTab
from ui.tabs.tahmin_tab import TahminTab
from ui.tabs.tahsilat_alacak_tab import TahsilatAlacakTab
from ui.tabs.trend_tab import TrendTab
from ui.worker import RaporWorker

INSTANCE_KEY = "MercanSoftware.MikRapor.SingleInstance"

# Sekme etiketleri tab sınıflarının BASLIK özniteliğinden gelir (tek kaynak):
# PDF/CSV dosya adları da aynı addan türetilir (bilesenler.rapor_slug).
# QTabBar '&'i mnemonic sayar; literal '&' için '&&' yazılır.


class HeaderTabBar(QTabBar):
    """Header nav — eşit genişlik; özel kurumsal tooltip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # İçeriğe göre genişlik (eşit-genişlik DEĞİL): eşitte "Bilanço" boşa yer harcar,
        # "Tahmin & Projeksiyon" gibi uzun etiket dar payına sığmayıp kırpılır.
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._font_px, self._dolgu = self._OLCEK_ADAYLARI[0]
        self._uyarlaniyor = False
        self._tip = NavTip()
        self._tip_idx = -1
        self._pending_idx = -1
        self.setMouseTracking(True)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(220)
        self._delay.timeout.connect(self._reveal_tip)

    # Grup ayraçları: CANLI sekmeler | RESMÎ (GL) sekmeler | Yapay Zekâ.
    # Tek sayı değil demet: üç gruplu düzende iki ayraç gerekiyor.
    _AYRAC_SONRASI: tuple[int, ...] = (5, 7)

    def minimumSizeHint(self) -> QSize:
        s = super().minimumSizeHint()
        s.setWidth(0)
        return s

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().paintEvent(event)
        from PyQt6.QtGui import QColor, QPainter, QPen
        cizilecek = [i for i in self._AYRAC_SONRASI
                     if self.count() > i + 1 and self.tabRect(i).isValid()]
        if not cizilecek:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor("#c3ccd8"))
        pen.setWidth(1)
        p.setPen(pen)
        for i in cizilecek:
            r = self.tabRect(i)
            inset = int(r.height() * 0.24)
            p.drawLine(r.right() + 1, r.top() + inset, r.right() + 1, r.bottom() - inset)
        p.end()

    # Dar pencerede denenecek (font px, yatay dolgu px) adayları — genişten dara.
    # İlk sığan seçilir; hiçbiri sığmazsa en dar olanla devam edilir (asla kırpılmaz).
    _OLCEK_ADAYLARI = ((13, 12), (13, 9), (12, 9), (12, 7), (11, 7), (11, 5), (10, 5))
    _MARJ = 4  # QSS 'margin: 0 2px' → sekme başına 4px

    def _olcu_fontu(self, px: int) -> QFontMetrics:
        f = QFont(self.font())
        f.setPixelSize(px)
        f.setWeight(QFont.Weight.ExtraBold)  # seçili sekme kalın; dar olana göre ölçme
        return QFontMetrics(f)

    def _sekme_genisligi(self, index: int, px: int, dolgu: int) -> int:
        metin = self.tabText(index).replace("&&", "&")
        return self._olcu_fontu(px).horizontalAdvance(metin) + 2 * dolgu + self._MARJ

    def _kullanilabilir_en(self) -> int:
        """
        Sekme çubuğunun sığması gereken gerçek genişlik.

        self.width() KULLANILMAZ: çubuğun genişliği kendi sizeHint'inden türüyor, o da
        seçilen fonta bağlı — döngüsel. Ölçüm dar pencerede bazen büyük fontla yapılıp
        sekmeler taşıyordu. Kapsayıcı (nav satırı) pencereden ölçeklendiği için sabittir.
        """
        ust = self.parentWidget()
        if ust is not None and ust.width() > 0:
            return max(0, ust.width() - 2 * self._MARJ)
        return self.width()

    def _uyarla(self) -> None:
        """Mevcut genişliğe sığacak en okunaklı (font, dolgu) çiftini seç ve uygula."""
        if self._uyarlaniyor or self.count() == 0:
            return
        mevcut = self._kullanilabilir_en()
        secim = self._OLCEK_ADAYLARI[-1]
        for px, dolgu in self._OLCEK_ADAYLARI:
            toplam = sum(self._sekme_genisligi(i, px, dolgu) for i in range(self.count()))
            if mevcut <= 0 or toplam <= mevcut:
                secim = (px, dolgu)
                break
        if secim == (self._font_px, self._dolgu):
            return
        self._font_px, self._dolgu = secim
        self._uyarlaniyor = True
        try:
            # Uygulama QSS'iyle birleşir; yalnız bu iki özelliği ezer (renk/kenar korunur).
            self.setStyleSheet(
                "QTabBar#headerTabBar::tab { padding: 9px %dpx; font-size: %dpx; }"
                % (self._dolgu, self._font_px)
            )
            self.updateGeometry()
        finally:
            self._uyarlaniyor = False

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().resizeEvent(event)
        self._uyarla()

    def showEvent(self, event) -> None:  # noqa: N802 — Qt API
        # Gösterim anında kapsayıcı nihai genişliğine ulaşmış olur; ilk ölçüm burada
        # kesinleşir (yalnız resizeEvent'e güvenmek dar pencerede taşmaya yol açıyordu).
        super().showEvent(event)
        self._uyarla()

    def tabSizeHint(self, index: int) -> QSize:  # noqa: N802 — Qt API
        # Genişlik etiket metninden hesaplanır (eşit-genişlik DEĞİL): eşitte "Bilanço"
        # boşa yer harcar, "Tahmin & Projeksiyon" gibi uzun etiket dar payına sığmayıp
        # kırpılırdı. Stilli QTabBar tüm sekmelere aynı hint'i verdiği için elle ölçeriz.
        # Genişlik yalnız KENDİ ölçümümüzden gelir; super()'inkiyle max ALINMAZ. Qt stil
        # sayfasını gecikmeli uyguladığı için super() bir süre ESKİ (geniş) dolguyu
        # döndürüyor; max onu tutunca sekmeler çubuğu aşıyordu — dar pencerede son
        # sekme görünmez oluyordu (testte ara ara yakalanan gerçek regresyon).
        base = super().tabSizeHint(index)
        base.setWidth(self._sekme_genisligi(index, self._font_px, self._dolgu))
        return base

    def event(self, event: QEvent) -> bool:  # noqa: N802 — Qt API
        if event.type() == QEvent.Type.ToolTip:
            return True
        return super().event(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        idx = self.tabAt(event.position().toPoint())
        if idx < 0:
            self._cancel_tip()
            return
        tip = self.tabToolTip(idx).strip()
        label = self.tabText(idx).strip()
        if not tip or tip == label:
            self._cancel_tip()
            return
        if idx == self._tip_idx and self._tip.isVisible():
            return
        self._pending_idx = idx
        self._delay.start()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._cancel_tip()
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._cancel_tip()
        super().hideEvent(event)

    def _reveal_tip(self) -> None:
        idx = self._pending_idx
        if idx < 0 or idx >= self.count():
            return
        tip = self.tabToolTip(idx).strip()
        label = self.tabText(idx).strip()
        if not tip or tip == label:
            return
        self._tip_idx = idx
        rect = self.tabRect(idx)
        anchor = self.mapToGlobal(rect.center())
        anchor.setY(self.mapToGlobal(rect.bottomLeft()).y() + 4)
        self._tip.show_text(tip, anchor, eyebrow="RAPOR")

    def _cancel_tip(self) -> None:
        self._delay.stop()
        self._pending_idx = -1
        self._tip_idx = -1
        self._tip.hide_tip()


def _try_activate_existing_instance() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_KEY)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"activate")
    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


def _bring_to_front(window: QMainWindow) -> None:
    if window.isMinimized():
        window.showNormal()
    window.show()
    window.raise_()
    window.activateWindow()


def _start_single_instance_server(window: QMainWindow) -> QLocalServer:
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.listen(INSTANCE_KEY)

    def _on_new() -> None:
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.waitForReadyRead(300)
            conn.readAll()
            conn.disconnectFromServer()
            _bring_to_front(window)

    server.newConnection.connect(_on_new)
    return server


class MikRaporWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{UYGULAMA_ADI} — {ALT_BASLIK}")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(960, 640)
        self.resize(1220, 840)
        self._donem = DonemDurumu()
        self._ping_worker: RaporWorker | None = None
        self._build()
        QTimer.singleShot(400, self._refresh_conn_status)

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("rootArea")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1) Marka bar — logo | ayarlar / bağlantı (sekmeler kendi satırında, altta)
        brand_bar = QFrame()
        brand_bar.setObjectName("brandBar")
        header = QHBoxLayout(brand_bar)
        header.setContentsMargins(2, 6, 2, 8)
        header.setSpacing(10)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        logo = QLabel()
        logo.setObjectName("brandMark")
        logo.setStyleSheet("background: transparent; border: none;")
        pm = app_logo_pixmap(40)
        if not pm.isNull():
            logo.setPixmap(pm)
            logo.setFixedSize(pm.size())
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)
        baslik = QLabel("MikRapor")
        baslik.setObjectName("titleLabel")
        titles.addWidget(baslik)
        header.addLayout(titles)

        # 2) Sekmeler — kendi tam-genişlik satırında; içerik ayrı stack
        #    (QTabWidget layout savaşmasın). Marka barının içinde DEĞİL: 8 sekme
        #    marka + ayarlar + firma rozetiyle aynı satıra sığmıyor (son iki sekme
        #    tamamen kesiliyordu); kendi satırında pencerenin tam genişliğini alır.
        self._tab_bar = HeaderTabBar()
        self._tab_bar.setObjectName("headerTabBar")

        self._stack = QStackedWidget()
        self._stack.setObjectName("raporStack")

        # SIRA, KİME GÖSTERİLDİĞİNE GÖRE. Program Bilanço ile açılıyordu: mali
        # müşavirin zaten her ay ürettiği, sahibi en az ilgilendiren tablo. Demo oradan
        # başlayınca ürün «bir muhasebe programı daha» gibi duruyor. Önce sahibin
        # sorduğu sorular gelir: kim bana borçlu, para nereden girip nereye çıktı.
        # Resmî iki tablo (kural 1b) sona alındı — ayrımın kendisi korunuyor, yalnız
        # sıralama tersine döndü.
        sekme_siniflari = (
            TahsilatAlacakTab,     # kim bana ne zaman ne kadar borçlu
            NakitAkisTab,          # para nereden girdi, nereye çıktı
            GercekDurumTab,
            TrendTab,
            TahminTab,
            ReelDegerTab,
            # ——— ayraç: buradan sonrası RESMÎ kayda dayanır (kural 1b)
            BilancoTab,
            GelirTablosuTab,
            # ——— ayraç: dışarıya veri gönderen tek sekme
            AiYorumTab,
        )
        for cls in sekme_siniflari:
            w = cls(self._donem)
            self._stack.addWidget(w)
            self._tab_bar.addTab(cls.BASLIK.replace("&", "&&"))

        self._tab_bar.currentChanged.connect(self._on_tab_degisti)

        nav = QFrame()
        nav.setObjectName("headerNav")
        nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(3, 3, 3, 3)
        nav_lay.setSpacing(0)
        nav_lay.addStretch(1)
        nav_lay.addWidget(self._tab_bar)
        nav_lay.addStretch(1)

        header.addStretch(1)

        # Düğme adı = pencere başlığı = metinlerde geçen ad. Üç ayrı ad («Ayarlar»,
        # «Mikro Bağlantı Ayarları», «Mikro Ayarları») kullanıcıya üç ayrı ekran
        # varmış izlenimi veriyordu (kural 5).
        btn_ayar = QPushButton(f" {AYARLAR_ADI}")
        btn_ayar.setObjectName("ghostBtn")
        btn_ayar.setIcon(icon_gear(14))
        btn_ayar.setIconSize(QSize(14, 14))
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Hakkında: yalnız ikon — marka barı zaten dolu, metin eklemek kalabalık yapardı.
        btn_hakkinda = QPushButton()
        btn_hakkinda.setObjectName("ghostBtn")
        btn_hakkinda.setIcon(icon_info(15))
        btn_hakkinda.setIconSize(QSize(15, 15))
        btn_hakkinda.setToolTip(f"{UYGULAMA_ADI} hakkında · sürüm ve iletişim")
        btn_hakkinda.clicked.connect(lambda: HakkindaDialog(self).exec())
        header.addWidget(btn_hakkinda, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._conn = QLabel()
        self._conn.setObjectName("connStatus")
        self._conn.setCursor(Qt.CursorShape.ArrowCursor)
        header.addWidget(self._conn, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._conn_tip = bagla_nav_tip(self._conn, eyebrow="BAĞLANTI", parent=self)
        layout.addWidget(brand_bar)
        layout.addWidget(nav)
        self._conn.setText("○  Ayarlanmadı")
        self._conn.setProperty("connected", False)

        # 3) Ortak chrome toolbar (aktif rapor araçları)
        self._chrome = ChromeToolbar(self._donem)
        self._chrome.getir_clicked.connect(self._on_chrome_getir)
        self._chrome.iptal_clicked.connect(self._on_chrome_iptal)
        self._chrome.pdf_clicked.connect(self._on_chrome_pdf)
        self._chrome.csv_clicked.connect(self._on_chrome_csv)
        self._chrome.ekstra_clicked.connect(self._on_chrome_ekstra)
        layout.addWidget(self._chrome)

        # 4) Sekme içerik alanı
        layout.addWidget(self._stack, stretch=1)
        self._on_tab_degisti(0)

    def _aktif_tab(self) -> RaporTab | None:
        w = self._stack.currentWidget()
        return w if isinstance(w, RaporTab) else None

    def _on_tab_degisti(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
        tab = self._aktif_tab()
        if tab is not None:
            tab.bagla_chrome(self._chrome)

    def _on_chrome_getir(self) -> None:
        tab = self._aktif_tab()
        if tab is not None:
            tab._on_getir()

    def _on_chrome_iptal(self) -> None:
        tab = self._aktif_tab()
        if tab is not None:
            tab._on_iptal()

    def _on_chrome_pdf(self) -> None:
        tab = self._aktif_tab()
        if tab is not None and tab.PDF_DESTEK:
            tab._on_pdf()

    def _on_chrome_csv(self) -> None:
        tab = self._aktif_tab()
        if tab is not None:
            tab._on_csv()

    def _on_chrome_ekstra(self) -> None:
        tab = self._aktif_tab()
        if tab is not None:
            tab._on_ekstra()

    def _set_conn(self, text: str, connected: bool, *, tooltip: str = "") -> None:
        self._conn.setText(text)
        self._conn.setToolTip("")  # native kapalı; NavTipBag kullan
        self._conn_tip.set_text(tooltip)
        self._conn.setProperty("connected", connected)
        self._conn.style().unpolish(self._conn)
        self._conn.style().polish(self._conn)

    def _refresh_conn_status(self) -> None:
        """Ayarlar eksikse ayarlanmadı; doluysa arka planda Mikro ping ile doğrula."""
        cfg = load_config()
        if not cfg.is_complete():
            self._set_conn("○  Ayarlanmadı", False)
            return
        self._set_conn("◌  Kontrol…", False)
        if self._ping_worker is not None and self._ping_worker.isRunning():
            self._ping_worker.iptal_et()
            self._ping_worker.wait(2000)

        def is_fn(bildir) -> MikroConfig:
            bildir("Ping…")
            MikroClient(cfg).ping()
            return cfg

        worker = RaporWorker(is_fn, self)
        self._ping_worker = worker
        worker.bitti.connect(self._on_ping_ok)
        worker.hata.connect(self._on_ping_hata)
        worker.finished.connect(lambda w=worker: self._on_ping_bitti(w))
        worker.start()

    def _on_ping_ok(self, cfg: object) -> None:
        if not isinstance(cfg, MikroConfig):
            return
        # Rozet BAĞLANTIYI gösterir, veritabanını değil. Firma kodu yazmak artık
        # yanlış bilgi: dönem iki yıla yayıldığında veri iki ayrı veritabanından
        # gelir (canlıda 20 → 2020-2025, 26 → 2026+) ve tek kod bunu gizlerdi.
        ad = (cfg.firma_adi or "").strip()
        self._set_conn("●  Bağlı", True,
                       tooltip=ad or "Veritabanı rapor dönemine göre seçilir.")

    def _on_ping_hata(self, _msg: str) -> None:
        self._set_conn("○  Bağlanılamadı", False)

    def _on_ping_bitti(self, worker: RaporWorker) -> None:
        if worker is self._ping_worker:
            self._ping_worker = None
        worker.deleteLater()

    def _on_ayarlar(self) -> None:
        if MikroAyarlarDialog(self).exec():
            self._refresh_conn_status()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt API
        if self._ping_worker is not None and self._ping_worker.isRunning():
            self._ping_worker.iptal_et()
            self._ping_worker.wait(3000)
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if isinstance(w, RaporTab):
                w.iptal_ve_bekle()
        event.accept()


def _ekrani_orantili_ac(window: QMainWindow, *, oran: float = 0.80) -> None:
    """Pencereyi ekranın ~oran kadarında, ortalanmış aç (tam ekran değil)."""
    screen = QApplication.primaryScreen()
    if screen is None:
        window.resize(1220, 840)
        window.show()
        return
    geo = screen.availableGeometry()
    w = min(geo.width(), max(window.minimumWidth(), int(geo.width() * oran)))
    h = min(geo.height(), max(window.minimumHeight(), int(geo.height() * oran)))
    x = geo.x() + (geo.width() - w) // 2
    y = geo.y() + (geo.height() - h) // 2
    window.setGeometry(x, y, w, h)
    window.show()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(app_icon())
    if _try_activate_existing_instance():
        return 0
    window = MikRaporWindow()
    # QLocalServer yaşam süresi uygulama kadar olmalı — del edilirse GC dinlemeyi keser
    window._single_instance_server = _start_single_instance_server(window)  # noqa: SLF001
    _ekrani_orantili_ac(window, oran=0.80)
    return app.exec()
