"""Ortak boş / karşılama ekranı — Teal A, emoji yok, markalı mark + tipografi."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.styles import ACCENT, FAINT, INK, MUTED


class _LedgerMark(QWidget):
    """Yumuşak ledger / bilanço illüstrasyonu (emoji yerine)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(120, 96)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Arka plan yumuşak teal disk
        grad = QLinearGradient(0, 0, 120, 96)
        grad.setColorAt(0.0, QColor("#ecfdf5"))
        grad.setColorAt(1.0, QColor("#e0f2fe"))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(8, 8, 104, 80), 16, 16)

        # Sayfa düzlemleri
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#d1d5db"), 1.2))
        p.drawRoundedRect(QRectF(28, 22, 52, 64), 4, 4)
        p.setBrush(QColor("#f8fafc"))
        p.drawRoundedRect(QRectF(40, 16, 52, 64), 4, 4)

        # Satır çizgileri
        pen = QPen(QColor(ACCENT))
        pen.setWidthF(1.6)
        p.setPen(pen)
        for i, y in enumerate((28, 38, 48, 58)):
            x2 = 78 if i % 2 == 0 else 68
            p.drawLine(QPointF(48, y), QPointF(x2, y))

        # Teal vurgu çubuğu
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(QRectF(48, 66, 30, 5), 2, 2)
        p.end()


def build_empty_state(baslik: str, aciklama: str, *, cta_hint: str = "Getir") -> QWidget:
    """Sekme boşken ortalanmış karşılama — marka + tek headline + kısa metin."""
    w = QWidget()
    w.setObjectName("emptyState")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 24, 32, 24)
    lay.setSpacing(0)
    lay.addStretch(2)

    mark = _LedgerMark()
    lay.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)
    lay.addSpacing(18)

    brand = QLabel("MikRapor")
    brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    brand.setStyleSheet(
        f"color: {ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 0.6px;"
    )
    lay.addWidget(brand)
    lay.addSpacing(6)

    title = QLabel(baslik)
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    title.setStyleSheet(f"color: {INK}; font-size: 24px; font-weight: 800;")
    lay.addWidget(title)
    lay.addSpacing(10)

    body = QLabel(aciklama)
    body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    body.setWordWrap(True)
    body.setMaximumWidth(480)
    body.setStyleSheet(f"color: {MUTED}; font-size: 14px; line-height: 150%;")
    lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
    lay.addSpacing(18)

    hint = QLabel(f"Dönemi seçin  →  {cta_hint}")
    hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    hint.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
    # CTA kısmını teal yapmak için rich text
    hint.setText(
        f"<span style='color:{FAINT};'>Dönemi seçin&nbsp; →&nbsp; "
        f"<b style='color:{ACCENT};'>{cta_hint}</b></span>"
    )
    hint.setTextFormat(Qt.TextFormat.RichText)
    lay.addWidget(hint)

    lay.addStretch(3)
    return w
