"""Ortak boş / karşılama ekranı — Design A mockup birebir: hero + marka + CTA."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.resources import app_logo_pixmap, asset_path
from ui.styles import ACCENT, INK, MUTED, NAVY


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
) -> QWidget:
    """Mockup A empty state: büyük hero, MikRapor lockup, headline, tek CTA."""
    w = QWidget()
    w.setObjectName("emptyState")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(48, 32, 48, 40)
    lay.setSpacing(0)
    lay.addStretch(3)

    art = QLabel()
    art.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    art.setObjectName("emptyArt")
    pix = QPixmap(str(asset_path("empty-hero.png")))
    if pix.isNull():
        pix = QPixmap(str(asset_path("empty-bilanco.png")))
    if not pix.isNull():
        art.setPixmap(
            pix.scaled(
                520,
                280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    lay.addWidget(art)
    lay.addSpacing(20)

    # Küçük marka lockup (mockup: ikon + MikRapor)
    brand_row = QHBoxLayout()
    brand_row.setSpacing(8)
    brand_row.addStretch(1)
    mark = QLabel()
    mark_pm = app_logo_pixmap(22)
    if not mark_pm.isNull():
        mark.setPixmap(mark_pm)
    brand_row.addWidget(mark)
    brand = QLabel("MikRapor")
    brand.setStyleSheet(
        f"color: {NAVY}; font-size: 14px; font-weight: 700; letter-spacing: 0.2px;"
    )
    brand_row.addWidget(brand)
    brand_row.addStretch(1)
    lay.addLayout(brand_row)
    lay.addSpacing(10)

    title = QLabel(baslik)
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    title.setStyleSheet(f"color: {ACCENT}; font-size: 30px; font-weight: 800;")
    lay.addWidget(title)
    lay.addSpacing(10)

    body = QLabel(aciklama)
    body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    body.setWordWrap(True)
    body.setMaximumWidth(540)
    body.setStyleSheet(f"color: {MUTED}; font-size: 14px; line-height: 155%;")
    lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
    lay.addSpacing(24)

    if on_cta is not None:
        btn = QPushButton(f"  {cta_hint}  ")
        btn.setObjectName("primaryBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumWidth(220)
        btn.setMinimumHeight(48)
        btn.setStyleSheet(
            f"QPushButton#primaryBtn {{ font-size: 15px; font-weight: 700; "
            f"padding: 12px 28px; border-radius: 10px; }}"
        )
        btn.clicked.connect(on_cta)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

    lay.addStretch(4)
    return w
