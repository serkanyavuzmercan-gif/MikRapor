"""Ortak üst chrome toolbar — Design A: marka bar (sekmeler) altında.

Satır 1: tarih + hızlı dönem + Getir + PDF/CSV + son güncelleme + durum
Satır 2: uzun rapor özeti chip şeridi (yalnız sonuç varken)
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.donem import KISAYOL_GRUPLARI, DonemDurumu, kisayol_aralik
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
_EXPORT_PASIF_TIP = "Önce «Raporu Getir» ile raporu yükleyin"


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
        self._kisayol_btn: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 8)
        root.setSpacing(8)

        # Sıra: tarih → hızlı dönem → Getir → PDF/CSV → (sağda durum)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._aralik = DonemAralikAlani(donem)
        row.addWidget(self._aralik)

        # Hızlı dönem — tarihin hemen yanında
        self._kisayol_grp = QButtonGroup(self)
        self._kisayol_grp.setExclusive(True)
        kisayol_serit = QHBoxLayout()
        kisayol_serit.setContentsMargins(0, 0, 0, 0)
        kisayol_serit.setSpacing(6)
        for grup in KISAYOL_GRUPLARI:
            kutu = QFrame()
            kutu.setObjectName("donemKisayol")
            kl = QHBoxLayout(kutu)
            kl.setContentsMargins(3, 2, 3, 2)
            kl.setSpacing(2)
            for kod, etiket, tip in grup:
                btn = QPushButton(etiket)
                btn.setObjectName("donemKisayolBtn")
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.setToolTip(tip)
                btn.clicked.connect(lambda _=False, k=kod: self._kisayol_uygula(k))
                self._kisayol_grp.addButton(btn)
                self._kisayol_btn[kod] = btn
                kl.addWidget(btn)
            kisayol_serit.addWidget(kutu)
        row.addLayout(kisayol_serit)

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
        self._btn_pdf.setObjectName("exportBtn")
        self._btn_pdf.setIcon(icon_pdf(15))
        self._btn_pdf.setIconSize(QSize(15, 15))
        self._btn_pdf.setCursor(Qt.CursorShape.ForbiddenCursor)
        self._btn_pdf.setProperty("hazir", "false")
        self._btn_pdf.setToolTip(_EXPORT_PASIF_TIP)
        self._btn_pdf.clicked.connect(self._pdf_tikla)
        row.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV")
        self._btn_csv.setObjectName("exportBtn")
        self._btn_csv.setIcon(icon_csv(15))
        self._btn_csv.setIconSize(QSize(15, 15))
        self._btn_csv.setCursor(Qt.CursorShape.ForbiddenCursor)
        self._btn_csv.setProperty("hazir", "false")
        self._btn_csv.setToolTip(_EXPORT_PASIF_TIP)
        self._btn_csv.clicked.connect(self._csv_tikla)
        row.addWidget(self._btn_csv)

        self._pdf_hazir = False
        self._csv_hazir = False

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

        donem.degisti.connect(self._kisayol_senkron)
        self._kisayol_senkron()

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
        self._btn_pdf.setToolTip("PDF olarak kaydet" if aktif else _EXPORT_PASIF_TIP)
        self._btn_pdf.setCursor(
            Qt.CursorShape.PointingHandCursor if aktif else Qt.CursorShape.ForbiddenCursor)

    def set_csv_aktif(self, aktif: bool) -> None:
        self._btn_csv.setEnabled(aktif)
        self._btn_csv.setToolTip("CSV olarak kaydet" if aktif else _EXPORT_PASIF_TIP)
        self._btn_csv.setCursor(
            Qt.CursorShape.PointingHandCursor if aktif else Qt.CursorShape.ForbiddenCursor)

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
            self._status.setText("Getirildi")
            self._status.setToolTip(text)
            self._status.setVisible(True)
            self._ozet_doldur(parts, renk)
        else:
            self._status.setText(_kisalt(text))
            self._status.setToolTip(text if len(text) > _KISA_MAX else "")
            self._status.setVisible(True)
            self._ozet_temizle()

    def _kisayol_uygula(self, kod: str) -> None:
        bas, bit = kisayol_aralik(kod)
        self._donem.donem_ayarla(bas=bas, bit=bit)
        self._kisayol_senkron()

    def _kisayol_senkron(self) -> None:
        """Mevcut dönem bir kısayola uyuyorsa o butonu işaretle."""
        bas, bit = self._donem.bas_tarih(), self._donem.bit_tarih()
        eslesen: str | None = None
        for grup in KISAYOL_GRUPLARI:
            for kod, _, _ in grup:
                k_bas, k_bit = kisayol_aralik(kod)
                if bas == k_bas and bit == k_bit:
                    eslesen = kod
                    break
            if eslesen is not None:
                break
        self._kisayol_grp.setExclusive(False)
        for kod, btn in self._kisayol_btn.items():
            btn.blockSignals(True)
            btn.setChecked(kod == eslesen)
            btn.blockSignals(False)
        self._kisayol_grp.setExclusive(True)

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
            fm = QFontMetrics(chip.font())
            if fm.horizontalAdvance(p) > 220:
                chip.setText(fm.elidedText(p, Qt.TextElideMode.ElideRight, 220))
            self._ozet_lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self._ozet_lay.addStretch(1)
        self._ozet.setVisible(True)
