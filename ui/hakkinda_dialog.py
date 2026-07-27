"""
Hakkında penceresi — künye, kısa tanıtım ve iletişim.

Bilgilerin tamamı infra/surum.py'den gelir; burada metin sabiti tutulmaz. Hata
bildirimi bağlantısı sürüm ve işletim sistemi bilgisini kendiliğinden taşır —
kullanıcıdan "hangi sürümü kullanıyorsunuz" diye sormak zorunda kalmayalım diye.
"""

from __future__ import annotations

import html

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from infra.surum import (
    ALT_BASLIK,
    GIZLILIK,
    ILETISIM,
    SURUM,
    TANITIM,
    TELIF,
    UYGULAMA_ADI,
    hata_bildirim_baglantisi,
    sistem_bilgisi,
)
from ui.resources import app_logo_pixmap
from ui.styles import ACCENT, BORDER, FAINT, INK, MUTED, PANEL_BG, SUBINK


class HakkindaDialog(QDialog):
    """Sürüm, telif, kısa tanıtım ve iletişim/hata bildirimi."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{UYGULAMA_ADI} Hakkında")
        self.setMinimumWidth(480)
        self._build_ui()

    # ------------------------------------------------------------------ kurulum
    def _build_ui(self) -> None:
        kok = QVBoxLayout(self)
        kok.setContentsMargins(22, 20, 22, 18)
        kok.setSpacing(14)

        kok.addLayout(self._baslik())
        kok.addWidget(self._metin(TANITIM, INK))
        kok.addWidget(self._kutu(GIZLILIK))
        kok.addWidget(self._iletisim())

        telif = self._metin(TELIF, FAINT, 11)
        telif.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        kok.addWidget(telif)

        dugmeler = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        kapat = dugmeler.button(QDialogButtonBox.StandardButton.Close)
        if kapat is not None:
            kapat.setText("Kapat")
        dugmeler.rejected.connect(self.reject)
        kok.addWidget(dugmeler)

    def _baslik(self) -> QHBoxLayout:
        satir = QHBoxLayout()
        satir.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(app_logo_pixmap(56))
        logo.setFixedSize(56, 56)
        satir.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)

        sag = QVBoxLayout()
        sag.setSpacing(2)
        ad = QLabel(UYGULAMA_ADI)
        ad.setStyleSheet(f"color:{INK}; font-size:22px; font-weight:800;")
        sag.addWidget(ad)
        sag.addWidget(self._metin(f"{ALT_BASLIK} · Sürüm {SURUM}", MUTED, 12))
        sag.addStretch(1)
        satir.addLayout(sag, 1)
        return satir

    @staticmethod
    def _metin(icerik: str, renk: str, boy: int = 13) -> QLabel:
        lbl = QLabel(icerik)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{renk}; font-size:{boy}px; background:transparent;")
        return lbl

    def _kutu(self, icerik: str) -> QFrame:
        kutu = QFrame()
        kutu.setObjectName("hakkindaKutu")
        kutu.setStyleSheet(
            f"QFrame#hakkindaKutu {{ background:{PANEL_BG}; border:1px solid {BORDER}; "
            f"border-left:3px solid {ACCENT}; border-radius:10px; }}")
        lay = QVBoxLayout(kutu)
        lay.setContentsMargins(13, 11, 13, 12)
        lay.addWidget(self._metin(icerik, SUBINK, 12))
        return kutu

    def _iletisim(self) -> QFrame:
        kutu = QFrame()
        lay = QVBoxLayout(kutu)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        bag = QLabel(
            f"<span style='color:{MUTED};'>İletişim ve hata bildirimi:</span> "
            f"<a href='mailto:{ILETISIM}' style='color:{ACCENT}; text-decoration:none;'>"
            f"<b>{html.escape(ILETISIM)}</b></a>")
        bag.setTextFormat(Qt.TextFormat.RichText)
        bag.setOpenExternalLinks(True)
        bag.setStyleSheet("font-size:13px; background:transparent;")
        lay.addWidget(bag)

        satir = QHBoxLayout()
        satir.setSpacing(8)

        # Hata bildirimi: konu ve ortam bilgisi hazır gelsin.
        self._btn_hata = QLabel(
            f"<a href='{hata_bildirim_baglantisi()}' "
            f"style='color:{ACCENT}; text-decoration:none;'>✉ Hata bildir ↗</a>")
        self._btn_hata.setTextFormat(Qt.TextFormat.RichText)
        self._btn_hata.setOpenExternalLinks(True)
        self._btn_hata.setStyleSheet("font-size:12px; background:transparent;")
        satir.addWidget(self._btn_hata)
        satir.addStretch(1)

        # E-posta istemcisi açılmayan makinelerde kullanıcı künyeyi elle yapıştırabilsin.
        self._btn_kopyala = QPushButton("Sistem bilgisini kopyala")
        self._btn_kopyala.setObjectName("ghostBtn")
        self._btn_kopyala.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_kopyala.clicked.connect(self._on_kopyala)
        satir.addWidget(self._btn_kopyala)
        lay.addLayout(satir)

        self._kunye = self._metin(sistem_bilgisi(), FAINT, 11)
        self._kunye.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._kunye)
        return kutu

    # -------------------------------------------------------------------- olay
    def _on_kopyala(self) -> None:
        pano = QGuiApplication.clipboard()
        if pano is not None:
            pano.setText(sistem_bilgisi())
        self._btn_kopyala.setText("Kopyalandı ✓")
