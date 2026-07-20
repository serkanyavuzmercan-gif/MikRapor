"""
MikRapor uygulama penceresi ve giriş noktası.

Design A düzeni: marka bar (sekmeler ortada) → ortak chrome toolbar → içerik.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QFont
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
from ui.chrome_toolbar import ChromeToolbar
from ui.donem import DonemDurumu
from ui.icons import icon_gear
from ui.mikro_settings_dialog import MikroAyarlarDialog
from ui.rapor_tab import RaporTab
from ui.resources import app_icon, app_logo_pixmap
from ui.styles import APP_STYLESHEET
from ui.tabs.bilanco_tab import BilancoTab
from ui.tabs.gelir_tablosu_tab import GelirTablosuTab
from ui.tabs.gercek_durum_tab import GercekDurumTab
from ui.tabs.nakit_akis_tab import NakitAkisTab
from ui.tabs.tahmin_tab import TahminTab
from ui.tabs.tahsilat_alacak_tab import TahsilatAlacakTab
from ui.tabs.trend_tab import TrendTab
from ui.worker import RaporWorker

INSTANCE_KEY = "MercanSoftware.MikRapor.SingleInstance"

# Kısa etiket + tam ad (tooltip) — header'da 7 sekme sığsın
_SEKME_ETIKETLERI = (
    ("Bilanço", "Anında Bilanço"),
    ("Gelir", "Gelir Tablosu"),
    ("Nakit & Kâr", "Nakit & Kârlılık"),
    ("Tahsilat", "Tahsilat & Alacak"),
    ("Nakit Akış", "Nakit Akış Analizi"),
    ("Tahmin", "Tahmin & Projeksiyon"),
    ("Trend", "Trend & Oranlar"),
)


class _NavTip(QFrame):
    """Header sekme hover — Windows’ta kararlı opak kurumsal kart (layered hata yok)."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("navTipCard")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Translucent + DropShadow Windows’ta UpdateLayeredWindowIndirect hatası verir
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 10, 6)
        root.setSpacing(7)

        accent = QFrame()
        accent.setObjectName("navTipAccent")
        accent.setFixedWidth(2)
        accent.setFixedHeight(20)
        root.addWidget(accent, alignment=Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._eyebrow = QLabel("RAPOR")
        self._eyebrow.setObjectName("navTipEyebrow")
        col.addWidget(self._eyebrow)
        self._title = QLabel()
        self._title.setObjectName("navTipTitle")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(title_font)
        col.addWidget(self._title)
        root.addLayout(col)

    def show_text(self, text: str, anchor_global: QPoint) -> None:
        self._title.setText(text)
        self.adjustSize()
        w, h = self.width(), self.height()
        x = int(anchor_global.x() - w // 2)
        y = int(anchor_global.y() + 6)
        # Ekran dışına taşmayı engelle
        screen = QApplication.screenAt(anchor_global) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.left() + 4, min(x, geo.right() - w - 4))
            y = max(geo.top() + 4, min(y, geo.bottom() - h - 4))
        self.move(x, y)
        self.show()
        self.raise_()

    def hide_tip(self) -> None:
        self.hide()


class HeaderTabBar(QTabBar):
    """Header nav — eşit genişlik; özel kurumsal tooltip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setExpanding(True)
        self.setDrawBase(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._tip = _NavTip()
        self._tip_idx = -1
        self._pending_idx = -1
        self.setMouseTracking(True)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(220)
        self._delay.timeout.connect(self._reveal_tip)

    def minimumSizeHint(self) -> QSize:
        s = super().minimumSizeHint()
        s.setWidth(0)
        return s

    def tabSizeHint(self, index: int) -> QSize:
        base = super().tabSizeHint(index)
        n = self.count()
        if n <= 0:
            return base
        w = max(1, self.width() // n) if self.width() > 0 else base.width()
        base.setWidth(w)
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
        # Sekmenin alt orta noktası
        anchor = self.mapToGlobal(rect.center())
        anchor.setY(self.mapToGlobal(rect.bottomLeft()).y() + 4)
        self._tip.show_text(tip, anchor)

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
        self.setWindowTitle("MikRapor — Finansal Raporlama")
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

        # 1) Marka bar — logo | sekmeler | ayarlar / bağlantı
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

        # 2) Sekmeler — tab bar header'da; içerik ayrı stack (QTabWidget layout savaşmasın)
        self._tab_bar = HeaderTabBar()
        self._tab_bar.setObjectName("headerTabBar")

        self._stack = QStackedWidget()
        self._stack.setObjectName("raporStack")

        sekme_siniflari = (
            BilancoTab,
            GelirTablosuTab,
            GercekDurumTab,
            TahsilatAlacakTab,
            NakitAkisTab,
            TahminTab,
            TrendTab,
        )
        for cls, (etiket, tam) in zip(sekme_siniflari, _SEKME_ETIKETLERI, strict=True):
            w = cls(self._donem)
            idx = self._stack.addWidget(w)
            self._tab_bar.addTab(etiket)
            self._tab_bar.setTabToolTip(idx, tam)

        self._tab_bar.currentChanged.connect(self._on_tab_degisti)

        nav = QFrame()
        nav.setObjectName("headerNav")
        nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(3, 3, 3, 3)
        nav_lay.setSpacing(0)
        nav_lay.addWidget(self._tab_bar, stretch=1)
        header.addWidget(nav, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        btn_ayar = QPushButton(" Ayarlar")
        btn_ayar.setObjectName("ghostBtn")
        btn_ayar.setToolTip("Mikro Ayarları")
        btn_ayar.setIcon(icon_gear(14))
        btn_ayar.setIconSize(QSize(14, 14))
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._conn = QLabel()
        self._conn.setObjectName("connStatus")
        header.addWidget(self._conn, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(brand_bar)
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

    def _set_conn(self, text: str, connected: bool) -> None:
        self._conn.setText(text)
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
        kod = cfg.firma_kodu or "—"
        ad = (cfg.firma_adi or "").strip()
        label = f"●  Firma {kod}" + (f" · {ad[:18]}" if ad else "")
        self._set_conn(label, True)

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
