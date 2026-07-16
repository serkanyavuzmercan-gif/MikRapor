"""Ortak boş / karşılama ekranı — Design A: illüstrasyon full-bleed arka plan + alt CTA bandı.

Mockup A (empty): büyük logomark + MikRapor, teal başlık, gri açıklama, dolu yeşil CTA.

Marka (logo+MikRapor) her sekmede aynı ayak izinde ortalanır; uzun başlık/CTA metinleri
yatayda ölçeklenerek sabit banda sığar — yazı uzunluğuna göre kayma / üst üste binme yok.
CTA: ikon+yazı tek grup olarak buton ortasında.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from ui.resources import app_logo_pixmap, asset_path
from ui.styles import ACCENT, ACCENT_HOVER, ACCENT_PRESSED, MUTED, NAVY

# Empty-state marka: mockup’ta toolbar’dan belirgin şekilde büyük
_MARK_SIZE = 44
# Gelir Tablosu empty (referans): sabit kompozisyon bandı — sekmeden sekmeye kaymasın
_COL_W = 480
_TITLE_MAX_W = 360   # "Gelir Tablosu" bandı; daha uzun başlık yatay ölçeklenir
_CTA_W = 300         # sabit CTA; uzun etiket yatay ölçeklenir, ikon+yazı ortada
_CTA_H = 48
_CTA_ICON = 16
_CTA_GAP = 8


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
        x = (self.width() - scaled.width()) // 2
        y = min(0, (self.height() - scaled.height()) // 3)
        p.drawPixmap(x, y, scaled)
        grad_h = max(140, int(self.height() * 0.42))
        for i in range(grad_h):
            t = i / max(1, grad_h - 1)
            alpha = int(230 * (t ** 1.8))
            p.fillRect(
                QRect(0, self.height() - grad_h + i, self.width(), 1),
                QColor(255, 255, 255, alpha),
            )
        p.end()


class _HScaleLabel(QWidget):
    """Tek satır metin — max_width aşarsa yalnızca yatayda ölçekler (yükseklik sabit)."""

    def __init__(
        self,
        text: str,
        *,
        color: str,
        point_size: int,
        weight: int = 800,
        max_width: int = _TITLE_MAX_W,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        self._font = QFont()
        self._font.setPixelSize(point_size)
        self._font.setWeight(QFont.Weight(weight) if weight >= 100 else QFont.Weight.Bold)
        self._font.setBold(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fm = QFontMetrics(self._font)
        self.setFixedSize(max_width, fm.height() + 6)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        p.setPen(self._color)
        fm = QFontMetrics(self._font)
        tw = fm.horizontalAdvance(self._text)
        if tw <= 0:
            p.end()
            return
        avail = float(self.width())
        sx = min(1.0, avail / tw)
        p.translate(avail / 2.0, 0.0)
        p.scale(sx, 1.0)
        p.translate(-tw / 2.0, 0.0)
        p.drawText(0, fm.ascent() + 3, self._text)
        p.end()


class _EmptyCtaButton(QPushButton):
    """Sabit boyutlu CTA — ikon + yazı tek grup olarak ortalanır; uzun yazı yatay ölçeklenir."""

    def __init__(self, text: str, icon: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = (text or "").strip()
        self._icon = icon
        self.setObjectName("emptyCtaBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_CTA_W, _CTA_H)
        self.setStyleSheet(f"""
            QPushButton#emptyCtaBtn {{
                background-color: {ACCENT};
                color: #ffffff;
                border: 1px solid {ACCENT};
                border-radius: 10px;
                padding: 0;
            }}
            QPushButton#emptyCtaBtn:hover {{
                background-color: {ACCENT_HOVER};
                border-color: {ACCENT_HOVER};
            }}
            QPushButton#emptyCtaBtn:pressed {{
                background-color: {ACCENT_PRESSED};
                border-color: {ACCENT_PRESSED};
            }}
        """)
        self._font = QFont()
        self._font.setPixelSize(15)
        self._font.setWeight(QFont.Weight.Bold)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(_CTA_W, _CTA_H)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Stil ile buton gövdesi (metin/ikon boş — kendimiz çizeriz)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.text = ""
        opt.icon = QIcon()
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, p, self)

        fm = QFontMetrics(self._font)
        text_w = fm.horizontalAdvance(self._label)
        pad = 20
        icon_slot = _CTA_ICON + (_CTA_GAP if not self._icon.isNull() else 0)
        text_avail = max(40.0, float(self.width() - 2 * pad - icon_slot))
        sx = min(1.0, text_avail / text_w) if text_w > 0 else 1.0
        scaled_text_w = text_w * sx
        group_w = icon_slot + scaled_text_w
        x0 = (self.width() - group_w) / 2.0
        cy = self.height() / 2.0

        if not self._icon.isNull():
            pix = self._icon.pixmap(QSize(_CTA_ICON, _CTA_ICON))
            p.drawPixmap(
                int(round(x0)),
                int(round(cy - _CTA_ICON / 2.0)),
                pix,
            )
            x0 += icon_slot

        # Metin: grup içinde, yatay ölçek merkezden; dikey orta
        p.setFont(self._font)
        p.setPen(QColor("#ffffff"))
        p.save()
        p.translate(x0 + scaled_text_w / 2.0, cy)
        p.scale(sx, 1.0)
        p.drawText(
            QRectF(-text_w / 2.0, -fm.height() / 2.0, text_w, fm.height()),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self._label,
        )
        p.restore()
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
        lay.setContentsMargins(48, 28, 48, 36)
        lay.setSpacing(0)
        lay.addStretch(6)

        # Sabit genişlik kolon — tüm sekmelerde aynı merkez ekseni
        col = QWidget()
        col.setObjectName("emptyCol")
        col.setFixedWidth(_COL_W)
        col.setStyleSheet("background: transparent;")
        col_lay = QVBoxLayout(col)
        col_lay.setContentsMargins(0, 0, 0, 0)
        col_lay.setSpacing(0)
        col_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Marka: logo + MikRapor — sabit ayak izi, kolon ortası
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_row.setContentsMargins(0, 0, 0, 0)
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
        brand_font = QFont()
        brand_font.setPixelSize(22)
        brand_font.setWeight(QFont.Weight.ExtraBold)
        brand.setFont(brand_font)
        brand.setStyleSheet(f"color: {NAVY}; letter-spacing: 0.15px; background: transparent;")
        brand.setFixedHeight(QFontMetrics(brand_font).height() + 8)
        brand_row.addWidget(brand, alignment=Qt.AlignmentFlag.AlignVCenter)
        brand_row.addStretch(1)
        col_lay.addLayout(brand_row)
        col_lay.addSpacing(14)

        title = _HScaleLabel(
            baslik, color=ACCENT, point_size=30, weight=800, max_width=_TITLE_MAX_W,
        )
        col_lay.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        col_lay.addSpacing(10)

        body = QLabel(aciklama)
        body.setObjectName("emptyBody")
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        body.setFixedWidth(_COL_W)
        body.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; line-height: 150%; background: transparent;"
            "padding: 0; margin: 0;"
        )
        self._body = body
        col_lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
        col_lay.addSpacing(24)

        if on_cta is not None:
            from ui.icons import icon_table

            btn = _EmptyCtaButton(cta_hint, icon_table(16, "#ffffff"))
            btn.clicked.connect(on_cta)
            col_lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        lay.addWidget(col, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(10)
        self._body_genislik_ayarla()

    def _body_genislik_ayarla(self) -> None:
        body = getattr(self, "_body", None)
        if body is None:
            return
        w = _COL_W
        body.setFixedWidth(w)
        h = body.heightForWidth(w)
        if h > 0:
            body.setMinimumHeight(h + 6)
            body.setMaximumHeight(16777215)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())
        self._overlay.setGeometry(self.rect())
        self._bg.lower()
        self._overlay.raise_()
        self._body_genislik_ayarla()


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
) -> QWidget:
    """Mockup A empty state — illüstrasyon ekranı kaplayan arka plan."""
    return EmptyState(baslik, aciklama, cta_hint=cta_hint, on_cta=on_cta)
