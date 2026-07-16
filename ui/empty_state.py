"""Ortak boş / karşılama ekranı — Design A mockup: hero + marka + tam metin + CTA."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from ui.resources import app_logo_pixmap, asset_path
from ui.styles import ACCENT, MUTED, NAVY


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
) -> QWidget:
    """Mockup A empty state: hero, MikRapor lockup, headline, alt metin (2 satır), CTA."""
    w = QWidget()
    w.setObjectName("emptyState")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 24, 40, 32)
    lay.setSpacing(0)
    lay.addStretch(2)

    art = QLabel()
    art.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    art.setObjectName("emptyArt")
    art.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    # Öncelik sırası: kullanıcının koyduğu anasayfalogo → paketteki hero → bilanço.
    pix = QPixmap()
    for ad in ("anasayfalogo.png", "empty-hero.png", "empty-bilanco.png"):
        pix = QPixmap(str(asset_path(ad)))
        if not pix.isNull():
            break
    if not pix.isNull():
        art.setPixmap(
            pix.scaled(
                480,
                240,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    lay.addWidget(art)
    lay.addSpacing(18)

    brand_row = QHBoxLayout()
    brand_row.setSpacing(8)
    brand_row.addStretch(1)
    mark = QLabel()
    mark_pm = app_logo_pixmap(20)
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
    lay.addSpacing(8)

    title = QLabel(baslik)
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    title.setStyleSheet(f"color: {ACCENT}; font-size: 28px; font-weight: 800;")
    lay.addWidget(title)
    lay.addSpacing(8)

    body = QLabel(aciklama)
    body.setObjectName("emptyBody")
    body.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
    body.setWordWrap(True)
    body.setMinimumWidth(420)
    body.setMaximumWidth(560)
    body.setMinimumHeight(44)  # 2 satır garantisi — kesilmesin
    body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
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

    lay.addStretch(3)
    return w
