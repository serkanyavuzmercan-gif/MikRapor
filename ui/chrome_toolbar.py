"""Ortak üst chrome toolbar — Design A: marka bar (sekmeler) altında.

Satır 1: tarih + Getir / PDF / CSV + son güncelleme + kısa durum
Satır 2: uzun rapor özeti chip şeridi (yalnız sonuç varken)

Dönem kısayolları (Bu ay / çeyrek / yıl) tarih seçici popup’ındadır.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.donem import DonemDurumu
from ui.icons import icon_csv, icon_pdf
from ui.styles import BAD, MUTED, OK, WARN
from ui.tarih_secici import DonemAralikAlani

_DURUM_RENK = {
    "notr": MUTED,
    "iyi": OK,
    "uyari": WARN,
    "hata": BAD,
}
_KISA_MAX = 44


def _kisalt(metin: str, maks: int = _KISA_MAX) -> str:
    t = (metin or "").strip()
    if len(t) <= maks:
        return t
    return t[: max(1, maks - 1)].rstrip(" ·,;") + "…"


class ChromeToolbar(QFrame):
    """Paylaşılan dönem + aksiyon şeridi + özet bandı."""

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
        self._son_tur = "notr"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 8)
        root.setSpacing(8)

        # —— Satır 1: kontroller + son güncelleme + kısa durum ——
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._aralik = DonemAralikAlani(donem)
        row.addWidget(self._aralik)

        self._btn_ekstra = QPushButton("Ayarlar")
        self._btn_ekstra.setObjectName("ghostBtn")
        self._btn_ekstra.setVisible(False)
        self._btn_ekstra.clicked.connect(self.ekstra_clicked.emit)
        row.addWidget(self._btn_ekstra)

        self._btn_getir = QPushButton("Raporu Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self.getir_clicked.emit)
        row.addWidget(self._btn_getir)

        self._btn_iptal = QPushButton("İptal")
        self._btn_iptal.setObjectName("ghostBtn")
        self._btn_iptal.setVisible(False)
        self._btn_iptal.clicked.connect(self.iptal_clicked.emit)
        row.addWidget(self._btn_iptal)

        self._btn_pdf = QPushButton("PDF")
        self._btn_pdf.setObjectName("ghostBtn")
        self._btn_pdf.setIcon(icon_pdf(15))
        self._btn_pdf.setIconSize(QSize(15, 15))
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self.pdf_clicked.emit)
        row.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setIcon(icon_csv(15))
        self._btn_csv.setIconSize(QSize(15, 15))
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self.csv_clicked.emit)
        row.addWidget(self._btn_csv)

        row.addStretch(1)

        self._son = QLabel("")
        self._son.setObjectName("sonGuncelleme")
        self._son.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._son.setVisible(False)
        row.addWidget(self._son)

        self._status = QLabel("")
        self._status.setObjectName("toolbarHint")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status.setWordWrap(False)
        self._status.setVisible(False)
        self._status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row.addWidget(self._status)
        root.addLayout(row)

        # —— Satır 2: özet chip şeridi ——
        self._ozet = QFrame()
        self._ozet.setObjectName("ozetSerit")
        self._ozet.setVisible(False)
        self._ozet_lay = QHBoxLayout(self._ozet)
        self._ozet_lay.setContentsMargins(2, 2, 2, 2)
        self._ozet_lay.setSpacing(8)
        self._ozet_lay.addStretch(1)
        root.addWidget(self._ozet)

    def set_aktif_tab(self, tab: object | None) -> None:
        """Chrome'u hangi sekmenin kontrol ettiğini kaydet."""
        self._aktif_tab = tab

    def aktif_tab(self) -> object | None:
        return self._aktif_tab

    def status_label(self) -> QLabel:
        """Geriye uyumluluk — asıl güncelleme set_durum ile yapılmalı."""
        return self._status

    def set_tek_tarih(self, tek: bool) -> None:
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

    def isaretle_son_guncelleme(self, when: datetime | None = None) -> None:
        """Başarılı rapor çekiminde sağdaki «Son: …» zaman damgasını günceller."""
        dt = when or datetime.now()
        self._son.setText(f"Son: {dt.strftime('%d.%m.%Y %H:%M')}")
        self._son.setToolTip(f"Son güncelleme: {dt.strftime('%d.%m.%Y %H:%M:%S')}")
        self._son.setVisible(True)

    def set_durum_mesaj(self, mesaj: str) -> None:
        self.set_durum(mesaj, self._son_tur)

    def set_durum(self, mesaj: str, tur: str = "notr") -> None:
        """Kısa durum sağda; « · » ile ayrılmış uzun özet alt şeritte chip olur."""
        self._son_tur = tur
        text = (mesaj or "").strip()
        renk = _DURUM_RENK.get(tur, MUTED)
        self._status.setStyleSheet(f"color: {renk}; font-weight: 600; font-size: 12px;")

        if not text:
            self._status.clear()
            self._status.setToolTip("")
            self._status.setVisible(False)
            self._ozet_temizle()
            return

        parts = [p.strip() for p in text.split(" · ") if p.strip()]
        if len(parts) >= 2:
            # Toolbar: kısa özet; şerit: chip'ler
            self._status.setText("Getirildi")
            self._status.setToolTip(text)
            self._status.setVisible(True)
            self._ozet_doldur(parts, renk)
        else:
            self._status.setText(_kisalt(text))
            self._status.setToolTip(text if len(text) > _KISA_MAX else "")
            self._status.setVisible(True)
            self._ozet_temizle()

    def _ozet_temizle(self) -> None:
        while self._ozet_lay.count():
            item = self._ozet_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._ozet_lay.addStretch(1)
        self._ozet.setVisible(False)

    def _ozet_doldur(self, parts: list[str], _renk: str) -> None:
        self._ozet_temizle()
        self._ozet_lay.takeAt(self._ozet_lay.count() - 1)  # stretch'i kaldır
        for p in parts[:6]:
            chip = QLabel(p)
            chip.setObjectName("ozetChip")
            chip.setToolTip(p)
            # Çok uzun chip metnini kısalt
            fm = QFontMetrics(chip.font())
            if fm.horizontalAdvance(p) > 220:
                chip.setText(fm.elidedText(p, Qt.TextElideMode.ElideRight, 220))
            self._ozet_lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self._ozet_lay.addStretch(1)
        self._ozet.setVisible(True)
