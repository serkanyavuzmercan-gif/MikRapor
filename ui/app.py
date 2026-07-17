"""
MikRapor uygulama penceresi ve giriş noktası.

Design A düzeni: marka bar (sekmeler ortada) → ortak chrome toolbar → içerik.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
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
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        # 1) Marka bar — logo | sekmeler | ayarlar / bağlantı
        brand_bar = QFrame()
        brand_bar.setObjectName("brandBar")
        header = QHBoxLayout(brand_bar)
        header.setContentsMargins(4, 4, 4, 0)
        header.setSpacing(10)
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        logo = QLabel()
        logo.setObjectName("brandMark")
        logo.setStyleSheet("background: transparent; border: none;")
        pm = app_logo_pixmap(52)
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
        alt = QLabel("Mikro finansal raporlar")
        alt.setObjectName("brandSubtitle")
        titles.addWidget(alt)
        header.addLayout(titles)

        # 2) Sekmeler (içerik pane aşağıda; tab bar marka bar ortasında)
        self._tabs = QTabWidget()
        self._tabs.setObjectName("raporTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(BilancoTab(self._donem), "Anında Bilanço")
        self._tabs.addTab(GelirTablosuTab(self._donem), "Gelir Tablosu")
        self._tabs.addTab(GercekDurumTab(self._donem), "Nakit && Kârlılık")
        self._tabs.addTab(TahsilatAlacakTab(self._donem), "Tahsilat && Alacak")
        self._tabs.addTab(NakitAkisTab(self._donem), "Nakit Akış")
        self._tabs.addTab(TahminTab(self._donem), "Tahmin")
        self._tabs.addTab(TrendTab(self._donem), "Trend && Oranlar")
        self._tabs.currentChanged.connect(self._on_tab_degisti)

        tab_bar = self._tabs.tabBar()
        tab_bar.setObjectName("headerTabBar")
        tab_bar.setExpanding(False)
        tab_bar.setDrawBase(False)
        tab_bar.setUsesScrollButtons(True)
        header.addWidget(tab_bar, stretch=1, alignment=Qt.AlignmentFlag.AlignBottom)

        btn_ayar = QPushButton(" Mikro Ayarları")
        btn_ayar.setObjectName("ghostBtn")
        btn_ayar.setIcon(icon_gear(15))
        btn_ayar.setIconSize(QSize(15, 15))
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._conn = QLabel()
        self._conn.setObjectName("connStatus")
        header.addWidget(self._conn, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(brand_bar)
        self._conn.setText("○  Bağlantı kontrol ediliyor…")
        self._conn.setProperty("connected", False)

        # 3) Ortak chrome toolbar (aktif rapor araçları)
        self._chrome = ChromeToolbar(self._donem)
        self._chrome.getir_clicked.connect(self._on_chrome_getir)
        self._chrome.iptal_clicked.connect(self._on_chrome_iptal)
        self._chrome.pdf_clicked.connect(self._on_chrome_pdf)
        self._chrome.csv_clicked.connect(self._on_chrome_csv)
        self._chrome.ekstra_clicked.connect(self._on_chrome_ekstra)
        layout.addWidget(self._chrome)

        # 4) Sekme içerik alanı (tab bar yukarıda)
        layout.addWidget(self._tabs, stretch=1)
        self._on_tab_degisti(0)

    def _aktif_tab(self) -> RaporTab | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, RaporTab) else None

    def _on_tab_degisti(self, _index: int) -> None:
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
            self._set_conn("○  Bağlantı ayarlanmadı", False)
            return
        self._set_conn("◌  Kontrol ediliyor…", False)
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
        label = f"●  Bağlı · Firma {kod}" + (f" · {ad[:28]}" if ad else "")
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
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
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
