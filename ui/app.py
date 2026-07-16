"""
MikRapor uygulama penceresi ve giriş noktası.

Sekmeli mimari: her finansal rapor kendi modülünde (ui/tabs/*), ortak iskelet
ui.rapor_tab.RaporTab. Ağ çağrıları arka plan thread'inde koşar (ui.worker).
Tek örnek (single instance): ikinci kopya açılınca mevcut pencere öne getirilir.
"""

from __future__ import annotations

import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.donem import DonemDurumu
from ui.mikro_settings_dialog import MikroAyarlarDialog
from ui.resources import app_icon, app_logo_pixmap
from ui.styles import LIGHT_STYLESHEET
from ui.tabs.bilanco_tab import BilancoTab
from ui.tabs.gelir_tablosu_tab import GelirTablosuTab
from ui.tabs.gercek_durum_tab import GercekDurumTab
from ui.tabs.nakit_akis_tab import NakitAkisTab
from ui.tabs.tahmin_tab import TahminTab
from ui.tabs.tahsilat_alacak_tab import TahsilatAlacakTab

INSTANCE_KEY = "MercanSoftware.MikRapor.SingleInstance"


# ---------------------------------------------------------------------------
# Tek örnek (single instance)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ana pencere
# ---------------------------------------------------------------------------

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

        # Üst bar: logo + MikRapor + global Mikro Ayarları
        header = QHBoxLayout()
        logo = QLabel()
        pm = app_logo_pixmap(40)
        if not pm.isNull():
            logo.setPixmap(pm)
            logo.setFixedSize(40, 40)
        header.addWidget(logo)
        baslik = QLabel("MikRapor")
        baslik.setObjectName("titleLabel")
        header.addWidget(baslik)
        alt = QLabel("Finansal Raporlama")
        alt.setStyleSheet("color: #6b7280; font-size: 12px; margin-left: 4px;")
        header.addWidget(alt)
        header.addStretch()
        btn_ayar = QPushButton("Mikro Ayarları")
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar)
        layout.addLayout(header)

        # Sekmeler — her rapor kendi modülünde (ortak dönem)
        self._tabs = QTabWidget()
        self._tabs.addTab(BilancoTab(self._donem), "Anında Bilanço")
        self._tabs.addTab(GelirTablosuTab(self._donem), "Gelir Tablosu")
        self._tabs.addTab(GercekDurumTab(self._donem), "Nakit && Kârlılık")
        self._tabs.addTab(TahsilatAlacakTab(self._donem), "Tahsilat && Alacak")
        self._tabs.addTab(NakitAkisTab(self._donem), "Nakit Akış")
        self._tabs.addTab(TahminTab(self._donem), "Tahmin")
        layout.addWidget(self._tabs, stretch=1)

    def _on_ayarlar(self) -> None:
        MikroAyarlarDialog(self).exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_STYLESHEET)
    app.setWindowIcon(app_icon())
    if _try_activate_existing_instance():
        return 0
    window = MikRaporWindow()
    server = _start_single_instance_server(window)
    del server
    window.showMaximized()
    return app.exec()
