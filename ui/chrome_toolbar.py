"""Ortak üst chrome toolbar — Design A: marka bar altında, sekmelerin üstünde.

Tarih / Getir / PDF / CSV / durum aktif sekmeye bağlanır; dönem DonemDurumu ile paylaşılır.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.donem import DonemDurumu, donem_aralik_bagla, donem_tek_bagla
from ui.styles import MUTED, OK
from ui.tarih_secici import TarihSecici


class ChromeToolbar(QFrame):
    """Paylaşılan dönem + aksiyon şeridi."""

    getir_clicked = pyqtSignal()
    iptal_clicked = pyqtSignal()
    pdf_clicked = pyqtSignal()
    csv_clicked = pyqtSignal()
    ekstra_clicked = pyqtSignal()

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tabToolbar")
        self._donem = donem
        self._tek_tarih = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        self._lbl_donem = QLabel("Dönem:")
        lay.addWidget(self._lbl_donem)

        self._tarih = TarihSecici(donem.bit_tarih(), genislik=140)
        lay.addWidget(self._tarih)

        self._bas = TarihSecici(donem.bas_tarih(), genislik=130)
        lay.addWidget(self._bas)
        self._ok = QLabel("→")
        lay.addWidget(self._ok)
        self._bit = TarihSecici(donem.bit_tarih(), genislik=130)
        lay.addWidget(self._bit)

        # Ayrı proxy'ler: tek-tarih ve aralık bağları _donem_uzaktan bayrağını paylaşmasın
        self._proxy_tek = QWidget(self)
        self._proxy_aralik = QWidget(self)
        donem_tek_bagla(self._proxy_tek, donem, self._tarih)
        donem_aralik_bagla(self._proxy_aralik, donem, self._bas, self._bit)

        self._btn_ekstra = QPushButton("Ayarlar")
        self._btn_ekstra.setObjectName("ghostBtn")
        self._btn_ekstra.setVisible(False)
        self._btn_ekstra.clicked.connect(self.ekstra_clicked.emit)
        lay.addWidget(self._btn_ekstra)

        self._btn_getir = QPushButton("Raporu Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self.getir_clicked.emit)
        lay.addWidget(self._btn_getir)

        self._btn_iptal = QPushButton("İptal")
        self._btn_iptal.setObjectName("ghostBtn")
        self._btn_iptal.setVisible(False)
        self._btn_iptal.clicked.connect(self.iptal_clicked.emit)
        lay.addWidget(self._btn_iptal)

        self._btn_pdf = QPushButton("📄 PDF")
        self._btn_pdf.setObjectName("ghostBtn")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self.pdf_clicked.emit)
        lay.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("▦ CSV")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self.csv_clicked.emit)
        lay.addWidget(self._btn_csv)

        lay.addStretch(1)

        self._status = QLabel("Hazır")
        self._status.setObjectName("toolbarHint")
        self._status.setStyleSheet(f"color: {OK}; font-weight: 600;")
        self._status.setWordWrap(False)
        lay.addWidget(self._status)

        self.set_tek_tarih(False)

    def status_label(self) -> QLabel:
        return self._status

    def set_tek_tarih(self, tek: bool) -> None:
        """Design A: chrome her zaman tarih aralığı gösterir (mockup: 01.01 — 16.07).

        tek=True sekmelerde (bilanço) fetch yine bitiş tarihini kullanır; UI aralık kalır.
        """
        self._tek_tarih = tek
        self._tarih.setVisible(False)
        self._bas.setVisible(True)
        self._ok.setVisible(True)
        self._bit.setVisible(True)
        self._lbl_donem.setVisible(False)
        # Ayırıcı mockup’taki "—" hissi
        self._ok.setText("—")
        self._ok.setStyleSheet(f"color: {MUTED}; font-weight: 600; padding: 0 2px;")

    def set_getir_etiket(self, text: str) -> None:
        # Design A: chrome her zaman "Raporu Getir"; sekme CTA empty state'te kalır
        del text
        self._btn_getir.setText("Raporu Getir")


    def set_pdf_gorunur(self, gorunur: bool) -> None:
        self._btn_pdf.setVisible(gorunur)

    def set_pdf_aktif(self, aktif: bool) -> None:
        self._btn_pdf.setEnabled(aktif)

    def set_csv_aktif(self, aktif: bool) -> None:
        self._btn_csv.setEnabled(aktif)

    def set_getir_aktif(self, aktif: bool) -> None:
        self._btn_getir.setEnabled(aktif)

    def set_iptal_gorunur(self, gorunur: bool) -> None:
        self._btn_iptal.setVisible(gorunur)

    def set_ekstra_gorunur(self, gorunur: bool, etiket: str = "Ayarlar") -> None:
        self._btn_ekstra.setText(etiket)
        self._btn_ekstra.setVisible(gorunur)

    def set_durum_mesaj(self, mesaj: str) -> None:
        self._status.setText(mesaj)
