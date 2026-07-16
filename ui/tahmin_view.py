"""
Tahmin — yerel Qt görünümü (projeksiyon çıktısı).

Varsayım formu sekmede (main.py) durur; burada tahmin SONUCU gösterilir: KPI, aylık projeksiyon
tablosu (ciro / brüt kâr / net kâr / nakit) ve ciro+nakit grafiği. Kart/satır stilleri paylaşılır.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.tahmin import Tahmin
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from ui.styles import PRIMARY_SOFT
from ui.gercek_durum_view import NEG, POZ, _card, _renk, _satir_label


def _tablo_panel(t: Tahmin) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    g.setColumnStretch(0, 1)

    for c, b in ((0, "Ay"), (1, "Ciro"), (2, "Brüt Kâr"), (3, "Net Kâr"), (4, "Nakit")):
        g.addWidget(_satir_label(b, renk=MUTED, boyut=11, bold=True,
                                 sag=(c != 0)), 0, c)
    r = 1
    for a in t.aylar:
        g.addWidget(_satir_label(a.ay, renk="#374151"), r, 0)
        g.addWidget(_satir_label(tl(a.ciro), sag=True), r, 1)
        g.addWidget(_satir_label(tl(a.brut_kar), sag=True), r, 2)
        g.addWidget(_satir_label(tl(a.net_kar), sag=True, renk=_renk(a.net_kar)), r, 3)
        g.addWidget(_satir_label(tl(a.nakit), sag=True, bold=True, renk=_renk(a.nakit)), r, 4)
        r += 1
    return _card("AYLIK PROJEKSİYON", inner)


class _TahminChart(QWidget):
    """Aylık ciro (çubuk) + nakit (çizgi) grafiği — QPainter."""

    def __init__(self, t: Tahmin, parent=None) -> None:
        super().__init__(parent)
        self._aylar = t.aylar
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        sol, sag, ust, alt = 8, 8, 14, 26
        cw, ch = w - sol - sag, h - ust - alt
        if not self._aylar or cw <= 0 or ch <= 0:
            p.setPen(QPen(QColor(FAINT)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Projeksiyon yok")
            p.end()
            return
        ciro = [a.ciro for a in self._aylar]
        nakit = [a.nakit for a in self._aylar]
        min_v = min(min(ciro, default=0.0), min(nakit, default=0.0), 0.0)
        max_v = max(max(ciro, default=0.0), max(nakit, default=0.0), 0.0)
        span = (max_v - min_v) or 1.0
        n = len(self._aylar)
        grup_w = cw / n
        bar_w = min(22.0, grup_w * 0.5)

        def y_of(v):
            return ust + ch * ((max_v - v) / span)

        p.setPen(QPen(QColor("#cbd5e1"), 1, Qt.PenStyle.DashLine))
        zy = y_of(0.0)
        p.drawLine(int(sol), int(zy), int(sol + cw), int(zy))
        # ciro çubukları
        for i, c in enumerate(ciro):
            cx = sol + grup_w * i + grup_w / 2
            vy = y_of(c)
            p.fillRect(QRectF(cx - bar_w / 2, min(vy, zy), bar_w, max(1.0, abs(vy - zy))),
                       QColor("#bfdbfe"))
        # nakit çizgisi
        p.setPen(QPen(QColor(ACCENT), 2))
        pts = []
        for i, nk in enumerate(nakit):
            cx = sol + grup_w * i + grup_w / 2
            pts.append((cx, y_of(nk)))
        for i in range(1, len(pts)):
            p.drawLine(int(pts[i - 1][0]), int(pts[i - 1][1]), int(pts[i][0]), int(pts[i][1]))
        p.setPen(QPen(QColor(MUTED)))
        p.setFont(QFont("Segoe UI", 7))
        for i, a in enumerate(self._aylar):
            ay_kisa = a.ay[2:] if len(a.ay) >= 7 else a.ay
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _grafik_panel(t: Tahmin) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:#99f6e4;'>■</span> Ciro (aylık) &nbsp;&nbsp;"
        f"<span style='color:{ACCENT};'>▬</span> Nakit (kümülatif)"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TahminChart(t))
    return _card("CİRO & NAKİT PROJEKSİYONU", inner)


def build_tahmin_widget(t: Tahmin, firma: str = "") -> QWidget:
    """Bir Tahmin'den QScrollArea içine konacak projeksiyon görünümü üretir."""
    content = QWidget()
    content.setObjectName("tahminContent")
    content.setStyleSheet("QWidget#tahminContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(24, 18, 24, 24)
    root.setSpacing(14)

    v = t.varsayim
    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    ilk = t.aylar[0].ay if t.aylar else ""
    son = t.aylar[-1].ay if t.aylar else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>TAHMİN &nbsp;·&nbsp; "
        f"{ilk} → {son} ({len(t.aylar)} ay){firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Varsayım: {v.ozet()}. "
        f"Senaryoyu üstteki alanlardan değiştirip «Projekte Et»e basın.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card(f"TOPLAM CİRO ({len(t.aylar)} AY)", tl(t.toplam_ciro), PRIMARY_SOFT, ACCENT))
    nk_bg, nk_vr = ("#e8f6ee", POZ) if t.toplam_net >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("TOPLAM NET KÂR", tl(t.toplam_net), nk_bg, nk_vr))
    sn_bg, sn_vr = ("#e8f6ee", POZ) if t.son_nakit >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("DÖNEM SONU NAKİT", tl(t.son_nakit), sn_bg, sn_vr))
    ed_bg, ed_vr = ("#fdecec", NEG) if t.en_dusuk_nakit < 0 else ("#fff7ed", "#b45309")
    kpi.addWidget(_kpi_card(f"EN DÜŞÜK NAKİT ({t.en_dusuk_ay})", tl(t.en_dusuk_nakit), ed_bg, ed_vr))
    root.addLayout(kpi)

    if t.en_dusuk_nakit < 0:
        uyari = QLabel(
            f"⚠ <b>Nakit {t.en_dusuk_ay} ayında eksiye düşüyor</b> ({tl(t.en_dusuk_nakit)}). "
            "Büyüme, marj veya gider varsayımını gözden geçirin ya da finansman planlayın."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdecec; border: 1px solid #f0b4b4; border-radius: 8px; "
            "color: #8a1c1c; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    root.addWidget(_grafik_panel(t))
    root.addWidget(_tablo_panel(t))
    root.addStretch(1)
    return content
