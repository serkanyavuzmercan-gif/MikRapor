"""Ortak boş / karşılama ekranı — Design A.

Üstte illüstrasyon (esnek), altta marka/başlık/CTA bandı (sabit yükseklik).
İki bölge asla üst üste binmez; pencere küçülünce yalnız illüstrasyon alanı daralır.
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
    QPainterPath,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.resources import app_logo_pixmap, asset_path
from ui.styles import ACCENT, ACCENT_HOVER, ACCENT_PRESSED, NAVY

_MARK_SIZE = 44
_COL_W = 480
_TITLE_MAX_W = 360
_BODY_MAX_W = 480
_BODY_H = 48          # sabit 2 satır — Tahmin (referans) satır aralığı
_BODY_COLOR = "#5c6b7a"  # referans açıklama gri (Tahmin empty)
_CTA_W = 300
_CTA_H = 48
_CTA_ICON = 16
_CTA_GAP = 8
_CTA_RADIUS = 10
_CTA_BOTTOM_PAD = 10   # alt yuvarlak kenar kesilmesin
_BOTTOM_PAD = 40
_GAP_BRAND_TITLE = 14
_GAP_TITLE_BODY = 10
_GAP_BODY_CTA = 24

# Sabit cluster yüksekliği (marka+başlık+açıklama+cta+araklıklar)
_BRAND_H = _MARK_SIZE
_TITLE_H = 36
_CLUSTER_H = (
    _BRAND_H + _GAP_BRAND_TITLE + _TITLE_H + _GAP_TITLE_BODY
    + _BODY_H + _GAP_BODY_CTA + _CTA_H + _CTA_BOTTOM_PAD
)

# Bilanço ile aynı varsayılan hero; sekme HERO_ASSET ile override edilir
DEFAULT_HERO_ASSET = "anasayfalogo.png"
_HERO_FALLBACKS = (
    "anasayfalogo.png",
    "mikrapor-hero-illustration.png",
    "empty-hero.png",
    "empty-bilanco.png",
)


def _load_hero_pixmap(asset: str | None = None) -> QPixmap:
    """Önce istenen asset; yoksa ortak fallback zinciri. Cover/soluk hep aynı widget'ta."""
    adaylar: list[str] = []
    if asset:
        adaylar.append(asset)
    for ad in _HERO_FALLBACKS:
        if ad not in adaylar:
            adaylar.append(ad)
    for ad in adaylar:
        pix = QPixmap(str(asset_path(ad)))
        if not pix.isNull():
            return pix
    return QPixmap()


class _CoverBackground(QWidget):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._src = pixmap
        self._opacity = 1.0
        self._soluk = False
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_soluk(self, soluk: bool, *, opacity: float = 0.26) -> None:
        """Rapor açıkken illüstrasyonu soluk arka plan yap."""
        self._soluk = soluk
        self._opacity = max(0.08, min(1.0, opacity)) if soluk else 1.0
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Soluk modda daha açık zemin; illüstrasyon düşük opaklıkla üstte
        p.fillRect(self.rect(), QColor("#eef3f7" if self._soluk else "#f7fafc"))
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
        p.setOpacity(self._opacity)
        p.drawPixmap(x, y, scaled)
        p.setOpacity(1.0)
        # Alttan beyaz geçiş; empty'de kısa (alt bant ayrı), solukken hafif
        if self._soluk:
            grad_h = max(60, int(self.height() * 0.18))
            max_a = 90
            exp = 1.2
        else:
            grad_h = max(72, int(self.height() * 0.20))
            max_a = 160
            exp = 1.5
        for i in range(grad_h):
            t = i / max(1, grad_h - 1)
            alpha = int(max_a * (t ** exp))
            p.fillRect(
                QRect(0, self.height() - grad_h + i, self.width(), 1),
                QColor(255, 255, 255, alpha),
            )
        p.end()


class _HScaleLabel(QWidget):
    """Tek satır — max_width aşarsa yatay ölçek; yükseklik sabit."""

    def __init__(
        self,
        text: str,
        *,
        color: str,
        point_size: int,
        weight: int = 800,
        max_width: int = _TITLE_MAX_W,
        height: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._color = QColor(color)
        self._font = QFont()
        self._font.setPixelSize(point_size)
        self._font.setWeight(QFont.Weight(weight) if weight >= 100 else QFont.Weight.Bold)
        if weight >= 700:
            self._font.setBold(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fm = QFontMetrics(self._font)
        self.setFixedSize(max_width, height if height is not None else fm.height() + 6)

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
        cy = self.height() / 2.0
        p.translate(avail / 2.0, cy)
        p.scale(sx, 1.0)
        p.drawText(
            QRectF(-tw / 2.0, -fm.height() / 2.0, tw, fm.height()),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self._text,
        )
        p.end()


class _HScaleBody(QWidget):
    """Açıklama — Tahmin empty referans stili: 14px regular, gri, ortalı, 2 satır.

    Sabit yükseklik; metin önce normal genişlikte kaydırılır (kısa/uzun aynı stil).
    2 satıra sığmazsa yatay ölçeklenir — dikey cluster kaymaz.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = " ".join((text or "").split())
        self._font = QFont()
        self._font.setPixelSize(14)
        self._font.setWeight(QFont.Weight.Normal)
        self._font.setBold(False)
        self.setFixedSize(_BODY_MAX_W, _BODY_H)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if not self._text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._font)
        p.setPen(QColor(_BODY_COLOR))
        fm = QFontMetrics(self._font)
        flags = int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap)

        # 1) Normal: sabit banda kelime kaydır (Tahmin stili — ölçek yok)
        br = fm.boundingRect(QRect(0, 0, _BODY_MAX_W, 10_000), flags, self._text)
        if br.height() <= _BODY_H + 2:
            opt = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            opt.setWrapMode(QTextOption.WrapMode.WordWrap)
            p.drawText(QRectF(0, 0, _BODY_MAX_W, _BODY_H), self._text, opt)
            p.end()
            return

        # 2) Uzun metin: 2 satıra sığacak daha geniş sanal satır → yatay ölçek
        lo, hi = _BODY_MAX_W, max(_BODY_MAX_W * 2, fm.horizontalAdvance(self._text) + 8)
        best = hi
        while lo <= hi:
            mid = (lo + hi) // 2
            mid_br = fm.boundingRect(QRect(0, 0, mid, 10_000), flags, self._text)
            if mid_br.height() <= _BODY_H + 2:
                best = mid
                hi = mid - 1
            else:
                lo = mid + 1
        sx = min(1.0, _BODY_MAX_W / max(1, best))
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.scale(sx, 1.0)
        p.translate(-best / 2.0, -_BODY_H / 2.0)
        opt = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        p.drawText(QRectF(0, 0, best, _BODY_H), self._text, opt)
        p.end()


class _EmptyCtaButton(QPushButton):
    """Sabit boyutlu CTA — ikon + yazı tek grup ortada; uzun yazı yatay ölçek.

    Alt kenar kesilmesin diye gövde kendi çizilir (stil CE_PushButton AA kırpmaz).
    """

    def __init__(self, text: str, icon: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Qt accelerator (&&) özel paint'te görünmesin → tek & veya /
        raw = (text or "").strip().replace("&&", " / ")
        self._label = " ".join(raw.split())
        self._icon = icon
        self.setObjectName("emptyCtaBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_CTA_W, _CTA_H)
        self.setFlat(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("QPushButton#emptyCtaBtn { background: transparent; border: none; padding: 0; }")
        self._font = QFont()
        self._font.setPixelSize(15)
        self._font.setWeight(QFont.Weight.Bold)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(_CTA_W, _CTA_H)

    def _bg_color(self) -> QColor:
        if self.isDown():
            return QColor(ACCENT_PRESSED)
        if self.underMouse():
            return QColor(ACCENT_HOVER)
        return QColor(ACCENT)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 0.5px inset — alt yuvarlak kenar kırpılmasın
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, float(_CTA_RADIUS), float(_CTA_RADIUS))
        p.fillPath(path, self._bg_color())

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
            p.drawPixmap(int(round(x0)), int(round(cy - _CTA_ICON / 2.0)), pix)
            x0 += icon_slot

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
    """Üstte illüstrasyon, altta sabit CTA bandı — örtüşme yok."""

    def __init__(
        self,
        baslik: str,
        aciklama: str,
        *,
        cta_hint: str = "Getir",
        on_cta: Callable[[], None] | None = None,
        hero_asset: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._arka_plan = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._bg = _CoverBackground(_load_hero_pixmap(hero_asset), self)
        root.addWidget(self._bg, stretch=1)

        # Alt bant: yazı/CTA — illüstrasyondan ayrı, asla üstüne binmez
        self._footer = QWidget(self)
        self._footer.setObjectName("emptyFooter")
        self._footer.setFixedHeight(_CLUSTER_H + _BOTTOM_PAD)
        self._footer.setStyleSheet(
            "QWidget#emptyFooter { background: #ffffff; border: none; }"
        )
        foot_lay = QVBoxLayout(self._footer)
        foot_lay.setContentsMargins(0, 0, 0, _BOTTOM_PAD)
        foot_lay.setSpacing(0)

        self._cluster = QWidget(self._footer)
        self._cluster.setObjectName("emptyCol")
        self._cluster.setFixedSize(_COL_W, _CLUSTER_H)
        self._cluster.setStyleSheet("background: transparent;")
        col_lay = QVBoxLayout(self._cluster)
        col_lay.setContentsMargins(0, 0, 0, 0)
        col_lay.setSpacing(0)
        col_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

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
        brand.setFixedHeight(_BRAND_H)
        brand_row.addWidget(brand, alignment=Qt.AlignmentFlag.AlignVCenter)
        brand_row.addStretch(1)
        col_lay.addLayout(brand_row)
        col_lay.addSpacing(_GAP_BRAND_TITLE)

        title = _HScaleLabel(
            baslik, color=ACCENT, point_size=30, weight=800,
            max_width=_TITLE_MAX_W, height=_TITLE_H,
        )
        col_lay.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        col_lay.addSpacing(_GAP_TITLE_BODY)

        body = _HScaleBody(aciklama)
        col_lay.addWidget(body, alignment=Qt.AlignmentFlag.AlignHCenter)
        col_lay.addSpacing(_GAP_BODY_CTA)

        if on_cta is not None:
            from ui.icons import icon_table

            btn = _EmptyCtaButton(cta_hint, icon_table(16, "#ffffff"))
            btn.clicked.connect(on_cta)
            col_lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            col_lay.addSpacing(_CTA_BOTTOM_PAD)
        else:
            col_lay.addSpacing(_CTA_H + _CTA_BOTTOM_PAD)

        foot_lay.addWidget(
            self._cluster,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        )
        root.addWidget(self._footer)

    def set_arka_plan_modu(self, aktif: bool) -> None:
        """True: yalnız soluk illüstrasyon (CTA bandı gizli)."""
        self._arka_plan = aktif
        self._footer.setVisible(not aktif)
        self._bg.set_soluk(aktif, opacity=0.24)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)


def build_soluk_arka_plan(*, opacity: float = 0.40, hero_asset: str | None = None) -> QWidget:
    """Rapor içeriği altında soluk illüstrasyon — tüm sekmelerde aynı cover/soluk motoru."""
    bg = _CoverBackground(_load_hero_pixmap(hero_asset or DEFAULT_HERO_ASSET))
    bg.set_soluk(True, opacity=opacity)
    return bg


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
    hero_asset: str | None = None,
) -> QWidget:
    return EmptyState(
        baslik,
        aciklama,
        cta_hint=cta_hint,
        on_cta=on_cta,
        hero_asset=hero_asset or DEFAULT_HERO_ASSET,
    )
