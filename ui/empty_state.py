"""Ortak boş / karşılama ekranı — Design A: büyük illüstrasyon + marka + CTA butonu."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.resources import asset_path
from ui.styles import ACCENT, FAINT, INK, MUTED


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
) -> QWidget:
    """Sekme boşken ortalanmış karşılama — illüstrasyon + headline + teal CTA."""
    w = QWidget()
    w.setObjectName("emptyState")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(40, 28, 40, 28)
    lay.setSpacing(0)
    lay.addStretch(2)

    art = QLabel()
    art.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    art.setObjectName("emptyArt")
    pix = QPixmap(str(asset_path("empty-bilanco.png")))
    if not pix.isNull():
        art.setPixmap(
            pix.scaled(
                220,
                220,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        art.setText("▦")
        art.setStyleSheet(f"color: {ACCENT}; font-size: 64px;")
    lay.addWidget(art)
    lay.addSpacing(16)

    brand = QLabel("MikRapor")
    brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    brand.setStyleSheet(
        f"color: {ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 0.8px;"
    )
    lay.addWidget(brand)
    lay.addSpacing(6)

    title = QLabel(baslik)
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    title.setStyleSheet(f"color: {INK}; font-size: 28px; font-weight: 800;")
    lay.addWidget(title)
    lay.addSpacing(10)

    body = QLabel(aciklama)
    body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    body.setWordWrap(True)
    body.setMaximumWidth(520)
    body.setStyleSheet(f"color: {MUTED}; font-size: 14px; line-height: 155%;")
    lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
    lay.addSpacing(22)

    if on_cta is not None:
        btn = QPushButton(cta_hint)
        btn.setObjectName("primaryBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumWidth(200)
        btn.setMinimumHeight(44)
        btn.clicked.connect(on_cta)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)
        hint = QLabel("veya üstteki dönem şeridinden getirin")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
        lay.addWidget(hint)
    else:
        hint = QLabel(
            f"<span style='color:{FAINT};'>Dönemi seçin&nbsp; →&nbsp; "
            f"<b style='color:{ACCENT};'>{cta_hint}</b></span>"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(hint)

    lay.addStretch(3)
    return w
