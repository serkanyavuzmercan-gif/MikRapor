"""Ortak üst chrome toolbar — Design A: marka bar altında, sekmelerin üstünde.

Tarih aralığı tek kutu (mockup: 01.01 — 16.07) + Getir / PDF / CSV / durum.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.donem import DonemDurumu
from ui.icons import icon_csv, icon_pdf
from ui.styles import OK
from ui.tarih_secici import DonemAralikAlani


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
        self._aktif_tab: object | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        self._aralik = DonemAralikAlani(donem)
        lay.addWidget(self._aralik)

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

        self._btn_pdf = QPushButton(" PDF")
        self._btn_pdf.setObjectName("ghostBtn")
        self._btn_pdf.setIcon(icon_pdf(15))
        self._btn_pdf.setIconSize(QSize(15, 15))
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self.pdf_clicked.emit)
        lay.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton(" CSV")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setIcon(icon_csv(15))
        self._btn_csv.setIconSize(QSize(15, 15))
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self.csv_clicked.emit)
        lay.addWidget(self._btn_csv)

        lay.addStretch(1)

        self._status = QLabel("Hazır")
        self._status.setObjectName("toolbarHint")
        self._status.setStyleSheet(f"color: {OK}; font-weight: 600;")
        self._status.setWordWrap(False)
        lay.addWidget(self._status)

    def set_aktif_tab(self, tab: object | None) -> None:
        """Chrome'u hangi sekmenin kontrol ettiğini kaydet."""
        self._aktif_tab = tab

    def aktif_tab(self) -> object | None:
        return self._aktif_tab

    def status_label(self) -> QLabel:
        return self._status

    def set_tek_tarih(self, tek: bool) -> None:
        """Bilanço tek tarih kullanır; UI yine aralık kutusu (mockup)."""
        self._tek_tarih = tek

    def set_getir_etiket(self, text: str) -> None:
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
