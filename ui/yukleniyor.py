"""
Rapor yüklenirken gösterilen ara ekran — dönen gösterge + canlı durum + iskelet kartlar.

Rapor sekmeleri (RaporTab) fetch sırasında boş/soluk hero'da takılı kalıyordu; kullanıcı
"program dondu mu?" hissediyordu. Bu ekran fetch boyunca gösterilir: dönen teal gösterge,
canlı durum satırı ("Banka/kasa hareketleri çekiliyor…") ve raporun yerleşimini taklit eden
iskelet kartlar. Tamamen kendi kendine çizilir (dış varlık/GIF yok). Zamanlayıcı yalnız görünür
ve aktifken çalışır — gizli sekmede CPU harcamaz.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QHideEvent, QPainter, QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.empty_state import build_soluk_arka_plan
from ui.resources import app_logo_pixmap
from ui.styles import ACCENT, BORDER, MUTED, NAVY, SUBINK


class _Spinner(QWidget):
    """Kendi çizilen dönen gösterge — 12 segment, baş açısı her tik döner."""

    _SEGMENT = 12
    _TICK_MS = 45

    def __init__(self, cap: int = 52, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cap = cap
        self._aci = 0
        self.setFixedSize(cap, cap)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tik)

    def basla(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def durdur(self) -> None:
        self._timer.stop()

    def _tik(self) -> None:
        self._aci = (self._aci + 1) % self._SEGMENT
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center()
        p.translate(c.x() + 0.5, c.y() + 0.5)
        dis_r = self._cap / 2.0 - 2.0
        ic_r = dis_r * 0.52
        kalinlik = max(3.0, self._cap * 0.085)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._SEGMENT):
            # Baştan uzaklaştıkça sönümlenen kuyruk
            uzaklik = (i - self._aci) % self._SEGMENT
            alpha = int(40 + 215 * (uzaklik / (self._SEGMENT - 1)))
            renk = QColor(ACCENT)
            renk.setAlpha(alpha)
            p.setBrush(renk)
            p.save()
            p.rotate(i * (360.0 / self._SEGMENT))
            p.drawRoundedRect(
                QRectF(-kalinlik / 2.0, -dis_r, kalinlik, dis_r - ic_r),
                kalinlik / 2.0, kalinlik / 2.0,
            )
            p.restore()
        p.end()


def _iskelet_kutu(yukseklik: int, *, radius: int = 10) -> QFrame:
    """Açık gri, yuvarlak köşeli iskelet bloğu (içerik gelene dek yer tutar)."""
    f = QFrame()
    f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    f.setFixedHeight(yukseklik)
    f.setStyleSheet(
        f"background: #eef1f5; border: 1px solid {BORDER}; border-radius: {radius}px;"
    )
    return f


class YukleniyorEkrani(QWidget):
    """Fetch boyunca gösterilen ara ekran; set_durum() ile canlı durum güncellenir."""

    def __init__(
        self,
        *,
        baslik: str = "Rapor hazırlanıyor…",
        hero_asset: str | None = None,
        hero_fit: str = "cover",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("yukleniyorEkrani")
        self._aktif = False

        kok = QGridLayout(self)
        kok.setContentsMargins(0, 0, 0, 0)
        kok.setSpacing(0)

        # Soluk hero arka plan — empty/rapor ile aynı görünüm
        arka = build_soluk_arka_plan(hero_asset=hero_asset, hero_fit=hero_fit)
        kok.addWidget(arka, 0, 0)

        # Ortadaki kart
        on = QWidget()
        on.setStyleSheet("background: transparent;")
        kok.addWidget(on, 0, 0)
        d = QVBoxLayout(on)
        d.setContentsMargins(40, 40, 40, 40)
        d.setSpacing(0)
        d.addStretch(1)

        kart = QFrame()
        kart.setObjectName("yukleniyorKart")
        kart.setStyleSheet(
            "QFrame#yukleniyorKart { background: rgba(255,255,255,0.94); "
            f"border: 1px solid {BORDER}; border-radius: 16px; }}"
        )
        kart.setMaximumWidth(560)
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(30, 26, 30, 26)
        kl.setSpacing(14)
        kl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Marka + dönen gösterge yan yana
        ust = QHBoxLayout()
        ust.setSpacing(14)
        ust.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._spinner = _Spinner(52)
        ust.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignVCenter)
        mark = QLabel()
        mark.setStyleSheet("background: transparent;")
        pm = app_logo_pixmap(34)
        if not pm.isNull():
            mark.setPixmap(pm)
            mark.setFixedSize(pm.size())
        ust.addWidget(mark, alignment=Qt.AlignmentFlag.AlignVCenter)
        marka_ad = QLabel("MikRapor")
        mf = QFont()
        mf.setPixelSize(20)
        mf.setWeight(QFont.Weight.ExtraBold)
        marka_ad.setFont(mf)
        marka_ad.setStyleSheet(f"color: {NAVY}; background: transparent;")
        ust.addWidget(marka_ad, alignment=Qt.AlignmentFlag.AlignVCenter)
        kl.addLayout(ust)

        self._baslik = QLabel(baslik)
        bf = QFont()
        bf.setPixelSize(18)
        bf.setWeight(QFont.Weight.Bold)
        self._baslik.setFont(bf)
        self._baslik.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        self._baslik.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        kl.addWidget(self._baslik)

        self._durum = QLabel("Veriler çekiliyor…")
        self._durum.setWordWrap(True)
        self._durum.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._durum.setStyleSheet(
            f"color: {SUBINK}; font-size: 13px; font-weight: 600; background: transparent;"
        )
        kl.addWidget(self._durum)

        ipucu = QLabel("Çok sayıda hareket varsa bu birkaç saniye sürebilir · üstteki «İptal» ile durdurabilirsiniz")
        ipucu.setWordWrap(True)
        ipucu.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ipucu.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        kl.addWidget(ipucu)

        # İskelet: 4 KPI kartı + 2 geniş bant (rapor yerleşimini taklit)
        kpi = QHBoxLayout()
        kpi.setSpacing(12)
        for _ in range(4):
            kpi.addWidget(_iskelet_kutu(58))
        kl.addSpacing(4)
        kl.addLayout(kpi)
        kl.addWidget(_iskelet_kutu(20, radius=6))
        kl.addWidget(_iskelet_kutu(20, radius=6))

        d.addWidget(kart, alignment=Qt.AlignmentFlag.AlignHCenter)
        d.addStretch(2)

    def set_durum(self, mesaj: str) -> None:
        if mesaj:
            self._durum.setText(mesaj)

    def basla(self) -> None:
        self._aktif = True
        if self.isVisible():
            self._spinner.basla()

    def durdur(self) -> None:
        self._aktif = False
        self._spinner.durdur()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._aktif:
            self._spinner.basla()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._spinner.durdur()
