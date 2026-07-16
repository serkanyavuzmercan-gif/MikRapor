"""Ortak boş / karşılama ekranı — Design A: illüstrasyon full-bleed arka plan + alt CTA bandı.

Mockup A (empty): büyük logomark + MikRapor, teal başlık, gri açıklama, dolu yeşil CTA.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.resources import app_logo_pixmap, asset_path
from ui.styles import ACCENT, ACCENT_HOVER, ACCENT_PRESSED, MUTED, NAVY

# Empty-state marka: mockup’ta toolbar’dan belirgin şekilde büyük
_MARK_SIZE = 44
_CTA_STYLE = f"""
QPushButton#emptyCtaBtn {{
    background-color: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT};
    font-size: 15px;
    font-weight: 700;
    padding: 14px 36px;
    border-radius: 10px;
    min-width: 240px;
    min-height: 48px;
}}
QPushButton#emptyCtaBtn:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
    color: #ffffff;
}}
QPushButton#emptyCtaBtn:pressed {{
    background-color: {ACCENT_PRESSED};
    border-color: {ACCENT_PRESSED};
    color: #ffffff;
}}
"""


def _load_hero_pixmap() -> QPixmap:
    """Öncelik: anasayfalogo → mikrapor-hero-illustration → empty-hero → empty-bilanco."""
    for ad in (
        "anasayfalogo.png",
        "mikrapor-hero-illustration.png",
        "empty-hero.png",
        "empty-bilanco.png",
    ):
        pix = QPixmap(str(asset_path(ad)))
        if not pix.isNull():
            return pix
    return QPixmap()


class _CoverBackground(QWidget):
    """İllüstrasyonu alanı kaplayacak şekilde çizer (CSS background-size: cover)."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._src = pixmap
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#f7fafc"))
        if self._src.isNull() or self.width() < 2 or self.height() < 2:
            p.end()
            return
        scaled = self._src.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Üste kaydır: illüstrasyon daha görünür (cover crop bias)
        x = (self.width() - scaled.width()) // 2
        y = min(0, (self.height() - scaled.height()) // 3)
        p.drawPixmap(x, y, scaled)
        # Alt ~40% yumuşak beyaz band — CTA okunaklı, üstte görsel baskın
        grad_h = max(140, int(self.height() * 0.42))
        for i in range(grad_h):
            t = i / max(1, grad_h - 1)
            alpha = int(230 * (t ** 1.8))
            p.fillRect(
                QRect(0, self.height() - grad_h + i, self.width(), 1),
                QColor(255, 255, 255, alpha),
            )
        p.end()


class EmptyState(QWidget):
    """Full-bleed hero arka plan; marka + başlık + açıklama + dolu yeşil CTA."""

    def __init__(
        self,
        baslik: str,
        aciklama: str,
        *,
        cta_hint: str = "Getir",
        on_cta: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._bg = _CoverBackground(_load_hero_pixmap(), self)
        self._bg.lower()

        self._overlay = QWidget(self)
        self._overlay.setObjectName("emptyOverlay")
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._overlay.setStyleSheet("background: transparent;")

        lay = QVBoxLayout(self._overlay)
        lay.setContentsMargins(48, 20, 48, 28)
        lay.setSpacing(0)
        # Üstte görsel; marka/başlık/CTA biraz daha yukarı (önce stretch 6 → alt band)
        lay.addStretch(3)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_row.addStretch(1)
        mark = QLabel()
        mark.setObjectName("emptyBrandMark")
        mark.setStyleSheet("background: transparent;")
        mark_pm = app_logo_pixmap(_MARK_SIZE)
        if not mark_pm.isNull():
            mark.setPixmap(mark_pm)
            mark.setFixedSize(mark_pm.size())
        brand_row.addWidget(mark, alignment=Qt.AlignmentFlag.AlignVCenter)
        brand = QLabel("MikRapor")
        brand.setObjectName("emptyBrandName")
        brand.setStyleSheet(
            f"color: {NAVY}; font-size: 22px; font-weight: 800; letter-spacing: 0.15px; "
            "background: transparent;"
        )
        brand_row.addWidget(brand, alignment=Qt.AlignmentFlag.AlignVCenter)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(14)

        title = QLabel(baslik)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 30px; font-weight: 800; background: transparent;"
        )
        lay.addWidget(title)
        lay.addSpacing(10)

        body = QLabel(aciklama)
        body.setObjectName("emptyBody")
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        body.setMinimumWidth(420)
        body.setMaximumWidth(560)
        body.setMinimumHeight(44)
        body.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; line-height: 150%; background: transparent;"
        )
        lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(24)

        if on_cta is not None:
            from PyQt6.QtCore import QSize

            from ui.icons import icon_table

            # Tam stylesheet: widget-level kısmi QSS app #primaryBtn arka planını bozuyordu
            btn = QPushButton(f" {cta_hint} ")
            btn.setObjectName("emptyCtaBtn")
            btn.setIcon(icon_table(16, "#ffffff"))
            btn.setIconSize(QSize(16, 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_CTA_STYLE)
            btn.clicked.connect(on_cta)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        lay.addStretch(2)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())
        self._overlay.setGeometry(self.rect())
        self._bg.lower()
        self._overlay.raise_()


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
) -> QWidget:
    """Mockup A empty state — illüstrasyon ekranı kaplayan arka plan."""
    return EmptyState(baslik, aciklama, cta_hint=cta_hint, on_cta=on_cta)
