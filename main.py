#!/usr/bin/env python3
"""
MikRapor — Mikro ERP finansal raporlama (PyQt6).

Sekmeli mimari: her finansal rapor kendi sekmesinde, kendi içinde bağımsız. İlk sekme
"Anında Bilanço" (Mikro GL'den tarih itibarıyla mizan→bilanço). Gelir Tablosu, Trend, oranlar
gibi raporlar ileride ayrı sekme olarak eklenir (BilancoTab desenini izleyerek).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bilanco_pdf import export_bilanco_pdf
from bilanco_view import build_bilanco_widget
from config import load_config
from mikro_api import MikroAPIError, MikroClient
from mikro_fetch import fetch_firma_adi, fetch_mizan
from mikro_settings_dialog import MikroAyarlarDialog
from mizan_bilanco import Bilanco, build_bilanco
from resources import app_icon, app_logo_pixmap
from styles import DARK_STYLESHEET

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

    def _on_new():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.waitForReadyRead(300)
            conn.readAll()
            conn.disconnectFromServer()
            _bring_to_front(window)

    server.newConnection.connect(_on_new)
    return server


# ---------------------------------------------------------------------------
# Anında Bilanço sekmesi
# ---------------------------------------------------------------------------

class BilancoTab(QWidget):
    """Tarih itibarıyla bilanço üreten bağımsız rapor sekmesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bilanco: Bilanco | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Tarih itibarıyla:"))
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd.MM.yyyy")
        self._date.setDate(QDate.currentDate())
        self._date.setFixedWidth(140)
        controls.addWidget(self._date)

        self._btn_getir = QPushButton("Bilanço Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_pdf = QPushButton("PDF Kaydet")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_pdf)
        controls.addWidget(self._btn_pdf)

        self._status = QLabel("Tarih seçip «Bilanço Getir»e basın.")
        self._status.setStyleSheet("color: #8b929e;")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addLayout(controls)

        self._empty = self._build_empty()
        layout.addWidget(self._empty, stretch=1)
        # Bilanço gövdesi yerel widget'larla (QTreeWidget) çizilir; satır :hover vurgusu
        # için zengin-metin yerine yerel görünüm. Dış scroll tüm sayfayı birlikte kaydırır.
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: #f4f6f9; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _build_empty(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch()
        lbl = QLabel(
            "<div align='center' style='font-family:Segoe UI;'>"
            "<div style='font-size:46px;'>📊</div>"
            "<div style='font-size:22px; font-weight:800; color:#374151; margin-top:6px;'>Anında Bilanço</div>"
            "<div style='color:#6b7280; margin-top:12px; line-height:160%;'>"
            "Mikro genel muhasebe verinizden, seçtiğiniz tarih itibarıyla<br>"
            "bilançoyu saniyeler içinde üretir.</div>"
            "<div style='color:#94a3b8; margin-top:16px; font-size:12px;'>"
            "Tarihi seçin&nbsp; →&nbsp; <b style='color:#2f6fed;'>Bilanço Getir</b>'e basın</div>"
            "</div>"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _selected_asof(self) -> str:
        return self._date.date().toString("yyyy-MM-dd")

    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return

        asof = self._selected_asof()
        self._btn_getir.setEnabled(False)
        self._status.setText(f"{self._date.date().toString('dd.MM.yyyy')} itibarıyla GL çekiliyor…")
        self._status.setStyleSheet("color: #8b929e;")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            rows = fetch_mizan(client, asof)
            self._bilanco = build_bilanco(rows, asof=asof)
            # Firma ünvanı: elle girilmişse o kazanır, boşsa Mikro'dan (FIRMALAR.fir_unvan) çek.
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Bilanço getirilemedi.")
            self._status.setStyleSheet("color: #e57373;")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        b = self._bilanco
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_bilanco_widget(b, firma=self._firma))
        self._btn_pdf.setEnabled(True)
        if abs(b.fark) < 1.0:
            self._status.setText(f"{len(rows)} hesap · Aktif=Pasif ✓ dengede.")
            self._status.setStyleSheet("color: #81c784;")
        elif b.dengede:
            self._status.setText(f"{len(rows)} hesap · ≈ dengede (kalan %{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet("color: #ffb74d;")
        else:
            self._status.setText(f"{len(rows)} hesap · FARK var (%{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet("color: #e57373;")

    def _on_pdf(self) -> None:
        if not self._bilanco:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"bilanco_{self._bilanco.asof}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_bilanco_pdf(self._bilanco, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._status.setText(f"PDF kaydedildi: {Path(path).name}")
        self._status.setStyleSheet("color: #81c784;")


def _yakinda_tab(baslik: str, aciklama: str) -> QWidget:
    """İleride eklenecek raporlar için 'yakında' yer tutucu sekmesi."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addStretch()
    lbl = QLabel(
        f"<div align='center' style='font-family:Segoe UI;'>"
        f"<div style='font-size:40px;'>🛠️</div>"
        f"<div style='font-size:20px; font-weight:800; color:#374151; margin-top:8px;'>{baslik}</div>"
        f"<div style='color:#6b7280; margin-top:10px; line-height:160%;'>{aciklama}</div>"
        f"<div style='color:#94a3b8; margin-top:12px; font-size:12px;'>yakında eklenecek</div>"
        f"</div>"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    lay.addStretch()
    return w


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
        alt.setStyleSheet("color: #8b929e; font-size: 12px; margin-left: 4px;")
        header.addWidget(alt)
        header.addStretch()
        btn_ayar = QPushButton("Mikro Ayarları")
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar)
        layout.addLayout(header)

        # Sekmeler — her rapor kendi sekmesinde
        self._tabs = QTabWidget()
        self._tabs.addTab(BilancoTab(), "Anında Bilanço")
        self._tabs.addTab(
            _yakinda_tab("Gelir Tablosu", "Net Satış → Brüt Kâr → Faaliyet Giderleri → Dönem Kâr/Zarar"),
            "Gelir Tablosu",
        )
        self._tabs.addTab(
            _yakinda_tab("Trend ve Oranlar", "Çok dönem karşılaştırma · cari oran · borçluluk · özkaynak"),
            "Trend ve Oranlar",
        )
        layout.addWidget(self._tabs, stretch=1)

    def _on_ayarlar(self) -> None:
        MikroAyarlarDialog(self).exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    app.setWindowIcon(app_icon())
    if _try_activate_existing_instance():
        return 0
    window = MikRaporWindow()
    server = _start_single_instance_server(window)
    del server
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
