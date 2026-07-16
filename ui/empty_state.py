"""Ortak boş / karşılama ekranı — Design A: illüstrasyon full-bleed arka plan + üstte CTA."""

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
from ui.styles import ACCENT, MUTED, NAVY


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
        # Soft fill under letterboxing if any
        p.fillRect(self.rect(), Qt.GlobalColor.white)
        if self._src.isNull() or self.width() < 2 or self.height() < 2:
            p.end()
            return
        scaled = self._src.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        # Altta hafif beyaz gradient bandı — metin okunaklı kalsın
        grad_h = max(160, self.height() // 2)
        for i in range(grad_h):
            t = i / max(1, grad_h - 1)
            alpha = int(210 * (t ** 1.35))
            p.fillRect(
                QRect(0, self.height() - grad_h + i, self.width(), 1),
                QColor(255, 255, 255, alpha),
            )
        p.end()


class EmptyState(QWidget):
    """Full-bleed hero arka plan; marka + başlık + açıklama + CTA üstte."""

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
        lay.setContentsMargins(40, 24, 40, 36)
        lay.setSpacing(0)
        lay.addStretch(5)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand_row.addStretch(1)
        mark = QLabel()
        mark.setStyleSheet("background: transparent;")
        mark_pm = app_logo_pixmap(20)
        if not mark_pm.isNull():
            mark.setPixmap(mark_pm)
        brand_row.addWidget(mark)
        brand = QLabel("MikRapor")
        brand.setStyleSheet(
            f"color: {NAVY}; font-size: 14px; font-weight: 700; letter-spacing: 0.2px; "
            "background: transparent;"
        )
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(8)

        title = QLabel(baslik)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 28px; font-weight: 800; background: transparent;"
        )
        lay.addWidget(title)
        lay.addSpacing(8)

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
        lay.addSpacing(22)

        if on_cta is not None:
            btn = QPushButton(f"  ▤  {cta_hint}  ")
            btn.setObjectName("primaryBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(230)
            btn.setMinimumHeight(48)
            btn.setStyleSheet(
                "QPushButton#primaryBtn { font-size: 15px; font-weight: 700; "
                "padding: 12px 28px; border-radius: 10px; }"
            )
            btn.clicked.connect(on_cta)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        lay.addSpacing(8)

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
