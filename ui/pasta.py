"""
Pasta (halka) grafik — ek bağımlılık olmadan QPainter ile çizilir.

Trend grafiğiyle aynı dil: hover'da dilim öne çıkar, açıklama listesi ayrı bir
mini tabloda durur (hover + zebra oradan gelir). Halkanın ortasında toplam yazar.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.gelir_tablosu import Dilim
from domain.mizan_bilanco import tl
from domain.ortak import yuzde
from ui.bilanco_view import _fit_height
from ui.gercek_durum_view import _agac, _c, _tsatir
from ui.styles import ACCENT, BORDER, FAINT, MUTED, PANEL_BG

# Gelir teal, gider navy: hangi pastaya baktığın renkten anlaşılsın.
GELIR_RENKLERI = ("#0f766e", "#0d9488", "#2dd4bf", "#5eead4", "#99f6e4", "#c7f2ec")
GIDER_RENKLERI = ("#1e3a5f", "#33578a", "#4f7cb3", "#7ba0cd", "#a9c2de", "#cfdcea")

_CAP = 214          # halkanın kutu boyu (kare)
_HALKA = 0.60       # iç yarıçap oranı


def _renk(renkler: tuple[str, ...], i: int) -> str:
    return renkler[i] if i < len(renkler) else renkler[-1]


def _kisa(v: float) -> str:
    """Halka ortası dar: 71.792.692 → '71,8 milyon'."""
    m = abs(v)
    if m >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f} milyar".replace(".", ",")
    if m >= 1_000_000:
        return f"{v / 1_000_000:.1f} milyon".replace(".", ",")
    return f"{v:,.0f}".replace(",", ".")


class Halka(QWidget):
    """Dilimleri saat 12'den başlayıp saat yönünde çizer; hover'da dilim büyür."""

    def __init__(self, dilimler: list[Dilim], renkler: tuple[str, ...],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dilimler = dilimler
        self._renkler = renkler
        self._vurgu = -1
        self.setFixedSize(_CAP, _CAP)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")

    # ------------------------------------------------------------------ olaylar
    def _dilim_indeksi(self, x: float, y: float) -> int:
        mx, my = self.width() / 2, self.height() / 2
        dis = min(mx, my) - 8
        uzak = math.hypot(x - mx, y - my)
        if not dis * _HALKA <= uzak <= dis + 4:
            return -1
        # saat 12 = 0°, saat yönünde artar
        aci = (math.degrees(math.atan2(x - mx, my - y)) + 360) % 360
        birikim = 0.0
        for i, d in enumerate(self._dilimler):
            birikim += d.pay * 3.6
            if aci <= birikim:
                return i
        return len(self._dilimler) - 1 if self._dilimler else -1

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802 — Qt API
        i = self._dilim_indeksi(ev.position().x(), ev.position().y())
        if i != self._vurgu:
            self._vurgu = i
            if i < 0:
                self.setToolTip("")
            else:
                d = self._dilimler[i]
                self.setToolTip(f"{d.etiket}\n{tl(d.tutar)}  ·  {yuzde(d.pay)}")
            self.update()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802 — Qt API
        if self._vurgu != -1:
            self._vurgu = -1
            self.update()
        super().leaveEvent(ev)

    # ------------------------------------------------------------------- çizim
    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mx, my = self.width() / 2, self.height() / 2
        dis = min(mx, my) - 8
        p.setPen(Qt.PenStyle.NoPen)

        bas = 90 * 16          # saat 12
        for i, d in enumerate(self._dilimler):
            yay = -d.pay * 3.6 * 16                    # eksi = saat yönü
            r = dis + 4 if i == self._vurgu else dis
            p.setBrush(QColor(_renk(self._renkler, i)))
            p.drawPie(QRectF(mx - r, my - r, 2 * r, 2 * r), int(bas), int(yay))
            bas += yay

        # Halkanın deliği: kart zeminiyle aynı renk → çember görüntüsü
        ic = dis * _HALKA
        p.setBrush(QColor(PANEL_BG))
        p.drawEllipse(QRectF(mx - ic, my - ic, 2 * ic, 2 * ic))

        toplam = sum(d.tutar for d in self._dilimler)
        p.setPen(QPen(QColor(MUTED)))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(mx - ic, my - 22, 2 * ic, 14),
                   Qt.AlignmentFlag.AlignCenter, "TOPLAM")
        p.setPen(QPen(QColor(ACCENT)))
        f = QFont("Segoe UI", 10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(mx - ic, my - 8, 2 * ic, 18),
                   Qt.AlignmentFlag.AlignCenter, _kisa(toplam))
        p.setPen(QPen(QColor(FAINT)))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(mx - ic, my + 10, 2 * ic, 14),
                   Qt.AlignmentFlag.AlignCenter, "TL")
        p.end()


def _liste(dilimler: list[Dilim], renkler: tuple[str, ...]) -> QWidget:
    t = _agac(4, [(0, 26), (2, 118), (3, 74)], esnek=1, hucre_renkli=True)
    # Son sütun varsayılan olarak esner; burada esneyecek olan AD sütunu (1) — yoksa
    # yüzde sütunu şişip hesap adları gereksiz yere kısalıyor.
    t.header().setStretchLastSection(False)
    t.setColumnWidth(3, 74)
    for i, d in enumerate(dilimler):
        _tsatir(t, [_c("■", renk=_renk(renkler, i)),
                    _c(d.etiket),
                    _c(tl(d.tutar), sag=True),
                    _c(yuzde(d.pay), kalin=True, sag=True)])
    _fit_height(t)
    return t


def pasta_karti(baslik: str, dilimler: list[Dilim], renkler: tuple[str, ...],
                *, dipnot: str = "") -> QFrame | None:
    """Tek dilimlik pasta bir şey anlatmaz — o durumda kart hiç kurulmaz."""
    if len(dilimler) < 2:
        return None

    card = QFrame()
    card.setObjectName("pastaCard")
    card.setStyleSheet(
        f"QFrame#pastaCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; "
        f"border-radius: 12px; }}"
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)

    lbl = QLabel(baslik)
    lbl.setStyleSheet(
        f"color: {ACCENT}; font-size: 14px; font-weight: 800; background: transparent;")
    lay.addWidget(lbl)

    govde = QHBoxLayout()
    govde.setSpacing(16)
    govde.addWidget(Halka(dilimler, renkler), 0, Qt.AlignmentFlag.AlignTop)
    govde.addWidget(_liste(dilimler, renkler), 1, Qt.AlignmentFlag.AlignVCenter)
    lay.addLayout(govde)

    if dipnot:
        d = QLabel(dipnot)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {FAINT}; font-size: 11px; background: transparent;")
        lay.addWidget(d)
    return card
