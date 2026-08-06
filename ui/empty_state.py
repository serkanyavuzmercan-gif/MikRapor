"""Ortak boş / karşılama ekranı — Design A: illüstrasyon full-bleed + alt CTA bandı.

Marka + başlık + açıklama + CTA sabit ayak izinde (alta sabitlenmiş).
Pencere yeniden boyutlanınca yalnız üstteki illüstrasyon alanı değişir; yazı/buton
bloğu kaymaz. Sekmeler arası fark: açıklama uzunluğu yatay ölçekle sığdırılır.
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
# Gövde yüksekliği SATIRLA ölçülür, piksel sabitiyle DEĞİL: Windows'ta sistem fontu
# Linux'un ~1,59 katı genişlikte çiziyor (sekme çubuğunda ölçüldü, bkz. ui/app.py),
# yani aynı metin orada daha çok satır tutuyor. Linux'ta tutturulmuş bir piksel
# tavanı kullanıcının gerçek ekranında metni yine sıkıştırırdı.
_BODY_SATIR = 3         # kısa açıklamaların referans yüksekliği
_BODY_SATIR_AZAMI = 12  # bundan uzun açıklama zaten kısaltılmalı (kural 4)
_ASGARI_OLCEK = 0.92    # bundan fazla yatay sıkıştırma okunmaz hâle getiriyor
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

# Cluster yüksekliği (marka+başlık+açıklama+cta+aralıklar)
_BRAND_H = _MARK_SIZE
_TITLE_H = 36


def _cluster_yuksekligi(body_h: int) -> int:
    """Cluster yüksekliği GÖVDEYE GÖRE — uzun açıklamada aşağı büyür.

    Sabit bir `_CLUSTER_H` vardı; gövde büyüyünce CTA kutunun dışında kalıyordu.
    Tek yükseklik kaynağı burasıdır ve gövdenin GERÇEK yüksekliğini ister —
    varsayılan bırakılsa yeni bir çağıran onu sessizce kullanır, hata geri gelirdi.
    """
    return (_BRAND_H + _GAP_BRAND_TITLE + _TITLE_H + _GAP_TITLE_BODY
            + body_h + _GAP_BODY_CTA + _CTA_H + _CTA_BOTTOM_PAD)


# Bilanço ile aynı varsayılan hero; sekme HERO_ASSET ile override edilir
DEFAULT_HERO_ASSET = "anasayfalogo.png"
# Empty + tablo-altı soluk illüstrasyon opaklığı (aynı görünüm)
HERO_SOLUK_OPACITY = 0.40
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
    def __init__(
        self,
        pixmap: QPixmap,
        parent: QWidget | None = None,
        *,
        fit: str = "cover",
    ) -> None:
        super().__init__(parent)
        self._src = pixmap
        self._fit = fit if fit in ("cover", "contain") else "cover"
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
        p.setClipRect(self.rect())
        # Soluk modda daha açık zemin; illüstrasyon düşük opaklıkla üstte
        p.fillRect(self.rect(), QColor("#eef3f7" if self._soluk else "#f7fafc"))
        if self._src.isNull() or self.width() < 2 or self.height() < 2:
            p.end()
            return
        if self._fit == "contain":
            # Yatayda doldur, dikeyde üstten; yan boşluk yok, taşan alt kırpılır
            scaled = self._src.scaledToWidth(
                self.width(),
                Qt.TransformationMode.SmoothTransformation,
            )
            x = 0
            y = 0
        else:
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
        # Alttan beyaz geçiş; solukken kısa ve hafif — illüstrasyon kaybolmasın
        if self._soluk:
            grad_h = max(60, int(self.height() * 0.18))
            max_a = 90
            exp = 1.2
        else:
            grad_h = max(140, int(self.height() * 0.42))
            max_a = 230
            exp = 1.8
        for i in range(grad_h):
            t = i / max(1, grad_h - 1)
            alpha = int(max_a * (t ** exp))
            p.fillRect(
                QRect(0, self.height() - grad_h + i, self.width(), 1),
                QColor(255, 255, 255, alpha),
            )
        p.end()


class _ClusterPanel(QWidget):
    """
    Marka/başlık/açıklama/CTA cluster'ının arkasına yarı şeffaf beyaz kart çizer.

    Hero illüstrasyonu tam opaklıkla (empty modda soluk değil) çizildiği için,
    illüstrasyonun parlak/yoğun kısımları (ör. AI ikonunun ışıklı halkası) yazının
    tam arkasına denk gelince metin okunmuyordu. Panel TÜM empty-state'lerde ortak
    (tek sekmeye özel yama değil) — hangi hero eklenirse eklensin metin garanti
    okunur kalsın diye.
    """

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 24, 24)
        p.fillPath(path, QColor(255, 255, 255, 158))
        p.end()
        super().paintEvent(_ev)


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
        satir = QFontMetrics(self._font).lineSpacing()
        self.taban = _BODY_SATIR * satir
        self.tavan = _BODY_SATIR_AZAMI * satir
        self._yukseklik = self._gereken_yukseklik()
        self.setFixedSize(_BODY_MAX_W, self._yukseklik)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def dogal_yukseklik(self, genislik: int = _BODY_MAX_W) -> int:
        """Metnin KIRPILMADAN istediği yükseklik (sınırsız).

        `tavan`ı aşıyorsa açıklama fazla uzundur: kutuya ancak yatay sıkıştırmayla
        girer, yani okunaklılık kaybıyla. Bekçi buna bakar ve `genislik`i daraltarak
        Windows'un geniş fontunu taklit eder — Linux'ta ölçen bir test o yolu hiç
        koşturmaz, kod bozulur ve yeşil kalırdı.
        """
        if not self._text:
            return self.taban
        fm = QFontMetrics(self._font)
        flags = int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap)
        return fm.boundingRect(
            QRect(0, 0, max(1, genislik), 10_000), flags, self._text
        ).height()

    def _gereken_yukseklik(self) -> int:
        """
        Metnin kaç satıra ihtiyacı varsa o kadar — üç satıra ZORLANMAZ.

        Eskiden yükseklik sabitti ve sığmayan metin yatay ölçekleniyordu. Kısa
        açıklamalarda sorun yoktu; Yapay Zekâ sekmesinin açıklaması 354, kilitliyken
        516 karakter olduğu için ölçek 0,5'in altına düşüyor ve yazı ekranda
        BÜSBÜTÜN OKUNMAZ hâle geliyordu (canlıda görüldü).
        """
        return max(self.taban, min(self.tavan, self.dogal_yukseklik()))

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if not self._text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._font)
        p.setPen(QColor(_BODY_COLOR))
        fm = QFontMetrics(self._font)
        flags = int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap)

        yuk = self._yukseklik
        # 1) Normal: kendi yüksekliğine kelime kaydır — ölçek yok
        br = fm.boundingRect(QRect(0, 0, _BODY_MAX_W, 10_000), flags, self._text)
        if br.height() <= yuk + 2:
            opt = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            opt.setWrapMode(QTextOption.WrapMode.WordWrap)
            p.drawText(QRectF(0, 0, _BODY_MAX_W, yuk), self._text, opt)
            p.end()
            return

        # 2) Azami yüksekliği de aşan metin: hafif yatay ölçek — ama OKUNAKLILIK
        # TABANININ altına inilmez. Sıkıştırıp okunmaz hâle getirmektense son satırı
        # üç noktayla kesmek yeğdir; kullanıcı zaten aynı metni balonda da görüyor.
        lo, hi = _BODY_MAX_W, max(_BODY_MAX_W * 2, fm.horizontalAdvance(self._text) + 8)
        best = hi
        while lo <= hi:
            mid = (lo + hi) // 2
            mid_br = fm.boundingRect(QRect(0, 0, mid, 10_000), flags, self._text)
            if mid_br.height() <= yuk + 2:
                best = mid
                hi = mid - 1
            else:
                lo = mid + 1
        sx = min(1.0, _BODY_MAX_W / max(1, best))
        if sx < _ASGARI_OLCEK:
            sx = 1.0
            best = _BODY_MAX_W
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.scale(sx, 1.0)
        p.translate(-best / 2.0, -yuk / 2.0)
        opt = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        p.drawText(QRectF(0, 0, best, yuk), self._text, opt)
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
    """Full-bleed hero; marka/başlık/açıklama/CTA alta sabitlenmiş sabit cluster."""

    def __init__(
        self,
        baslik: str,
        aciklama: str,
        *,
        cta_hint: str = "Getir",
        on_cta: Callable[[], None] | None = None,
        hero_asset: str | None = None,
        hero_fit: str = "cover",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._bg = _CoverBackground(
            _load_hero_pixmap(hero_asset), self, fit=hero_fit,
        )
        self._bg.lower()
        self._arka_plan = False

        # Açıklama ÖNCE kurulur: cluster yüksekliği onun gerçek yüksekliğinden türer.
        # Sabit yükseklik kullanılsaydı uzun açıklama kutunun dışında kalırdı — kural 2:
        # sığmayan metni sıkıştırıp okunmaz hâle getirmek de, kırpmak da kabul edilmez.
        body = _HScaleBody(aciklama)
        self._cluster_h = _cluster_yuksekligi(body.height())

        # Cluster — layout stretch yok; resizeEvent ile alta sabitlenir
        self._cluster = _ClusterPanel(self)
        self._cluster.setObjectName("emptyCol")
        self._cluster.setFixedSize(_COL_W, self._cluster_h)
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

        self._yerlestir()

    def set_arka_plan_modu(self, aktif: bool) -> None:
        """True: rapor içeriği altında soluk illüstrasyon; marka/CTA gizlenir."""
        self._arka_plan = aktif
        self._cluster.setVisible(not aktif)
        self._bg.set_soluk(aktif, opacity=0.24)
        self._yerlestir()

    def _yerlestir(self) -> None:
        """Cluster'ı yatay ortala, dikeyde alta sabitle — resize yalnızca üst boşluğu değiştirir."""
        self._bg.setGeometry(self.rect())
        self._bg.lower()
        if self._arka_plan:
            return
        # isVisible() kullanma: gizli sekmede ata gizliyken False döner, yerleşim kaçardı
        w = max(1, self.width())
        h = max(1, self.height())
        x = (w - _COL_W) // 2
        y = max(8, h - _BOTTOM_PAD - self._cluster_h)
        self._cluster.setGeometry(x, y, _COL_W, self._cluster_h)
        self._cluster.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._yerlestir()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        # Gizli sekme ilk açılınca resize kaçabiliyor — yerleşimi burada da uygula
        super().showEvent(event)
        self._yerlestir()


def build_soluk_arka_plan(
    *,
    opacity: float = HERO_SOLUK_OPACITY,
    hero_asset: str | None = None,
    hero_fit: str = "cover",
) -> QWidget:
    """Rapor içeriği altında soluk illüstrasyon — empty ile aynı solukluk."""
    bg = _CoverBackground(
        _load_hero_pixmap(hero_asset or DEFAULT_HERO_ASSET), fit=hero_fit,
    )
    bg.set_soluk(True, opacity=opacity)
    return bg


def build_empty_state(
    baslik: str,
    aciklama: str,
    *,
    cta_hint: str = "Getir",
    on_cta: Callable[[], None] | None = None,
    hero_asset: str | None = None,
    hero_fit: str = "cover",
) -> QWidget:
    return EmptyState(
        baslik,
        aciklama,
        cta_hint=cta_hint,
        on_cta=on_cta,
        hero_asset=hero_asset or DEFAULT_HERO_ASSET,
        hero_fit=hero_fit,
    )
