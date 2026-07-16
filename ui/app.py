"""
MikRapor uygulama penceresi ve giriş noktası.

Design A düzeni: marka bar → ortak chrome toolbar → sekmeler → içerik.
"""

from __future__ import annotations

import sys

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

from infra.config import load_config
from ui.chrome_toolbar import ChromeToolbar
from ui.donem import DonemDurumu
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
        self.setMinimumSize(1080, 720)
        self.resize(1220, 840)
        self._donem = DonemDurumu()
        self._build()

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("rootArea")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # 1) Marka bar
        brand_bar = QFrame()
        brand_bar.setObjectName("brandBar")
        header = QHBoxLayout(brand_bar)
        header.setContentsMargins(4, 2, 4, 8)
        header.setSpacing(12)
        logo = QLabel()
        pm = app_logo_pixmap(48)
        if not pm.isNull():
            logo.setPixmap(pm)
            logo.setFixedSize(48, 48)
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
        header.addStretch()
        btn_ayar = QPushButton("⚙  Mikro Ayarları")
        btn_ayar.setObjectName("ghostBtn")
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar)
        self._conn = QLabel()
        self._conn.setObjectName("connStatus")
        header.addWidget(self._conn)
        layout.addWidget(brand_bar)
        self._refresh_conn_status()

        # 2) Ortak chrome toolbar (Design A — sekmelerin ÜSTÜNDE)
        self._chrome = ChromeToolbar(self._donem)
        self._chrome.getir_clicked.connect(self._on_chrome_getir)
        self._chrome.iptal_clicked.connect(self._on_chrome_iptal)
        self._chrome.pdf_clicked.connect(self._on_chrome_pdf)
        self._chrome.csv_clicked.connect(self._on_chrome_csv)
        self._chrome.ekstra_clicked.connect(self._on_chrome_ekstra)
        layout.addWidget(self._chrome)

        # 3) Sekmeler
        self._tabs = QTabWidget()
        self._tabs.addTab(BilancoTab(self._donem), "Anında Bilanço")
        self._tabs.addTab(GelirTablosuTab(self._donem), "Gelir Tablosu")
        self._tabs.addTab(GercekDurumTab(self._donem), "Nakit && Kârlılık")
        self._tabs.addTab(TahsilatAlacakTab(self._donem), "Tahsilat && Alacak")
        self._tabs.addTab(NakitAkisTab(self._donem), "Nakit Akış")
        self._tabs.addTab(TahminTab(self._donem), "Tahmin")
        self._tabs.currentChanged.connect(self._on_tab_degisti)
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

    def _refresh_conn_status(self) -> None:
        cfg = load_config()
        if cfg.is_complete():
            kod = cfg.firma_kodu or "—"
            ad = (cfg.firma_adi or "").strip()
            label = f"●  Bağlı · Firma {kod}" + (f" · {ad[:28]}" if ad else "")
            self._conn.setText(label)
            self._conn.setProperty("connected", True)
        else:
            self._conn.setText("○  Bağlantı ayarlanmadı")
            self._conn.setProperty("connected", False)
        self._conn.style().unpolish(self._conn)
        self._conn.style().polish(self._conn)

    def _on_ayarlar(self) -> None:
        if MikroAyarlarDialog(self).exec():
            self._refresh_conn_status()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(app_icon())
    if _try_activate_existing_instance():
        return 0
    window = MikRaporWindow()
    server = _start_single_instance_server(window)
    del server
    window.showMaximized()
    return app.exec()
