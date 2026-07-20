"""
Trend & Oranlar — yerel Qt görünümü.

Aylık satış/alış/brüt/nakit trend grafiği + bilançodan türetilen finansal oranlar.
Grafik ek bağımlılık olmadan QPainter ile çizilir (Nakit & Kârlılık ile aynı dil).
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
from domain.trend import TrendRapor
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG
from ui.styles import BAD as NEG
from ui.styles import BORDER, PANEL_BG
from ui.styles import OK as POZ


def _renk(v: float) -> str:
    return POZ if v >= 0 else NEG


def _card(baslik: str, inner: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("trCard")
    card.setStyleSheet(
        f"QFrame#trCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}"
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    lbl = QLabel(baslik)
    lbl.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: 800; background: transparent;")
    lay.addWidget(lbl)
    lay.addWidget(inner)
    return card


def _satir_label(text: str, *, renk: str = "#374151", bold: bool = False,
                 boyut: int = 12, sag: bool = False) -> QLabel:
    lbl = QLabel(text)
    w = "800" if bold else "400"
    lbl.setStyleSheet(
        f"color: {renk}; font-size: {boyut}px; font-weight: {w}; background: transparent;"
    )
    if sag:
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


class _TrendChart(QWidget):
    """Aylık Satış, Brüt Kâr ve Net Nakit çubuk grafiği."""

    def __init__(self, tr: TrendRapor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._aylar = tr.aylik
        self.setMinimumHeight(220)
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
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Trend için veri yok")
            p.end()
            return

        seriler = [(a.satis, a.brut, a.nakit_net) for a in self._aylar]
        min_v = min((min(s, b, n) for s, b, n in seriler), default=0.0)
        max_v = max((max(s, b, n) for s, b, n in seriler), default=0.0)
        min_v = min(min_v, 0.0)
        max_v = max(max_v, 0.0)
        span = (max_v - min_v) or 1.0

        n = len(self._aylar)
        grup_w = cw / n
        bar_w = min(18.0, grup_w / 4.2)
        renkler = (QColor(ACCENT), QColor(POZ), QColor("#d97706"))

        def y_of(v: float) -> float:
            return ust + ch * ((max_v - v) / span)

        p.setPen(QPen(QColor("#cbd5e1"), 1, Qt.PenStyle.DashLine))
        zy = y_of(0.0)
        p.drawLine(int(sol), int(zy), int(sol + cw), int(zy))

        p.setFont(QFont("Segoe UI", 7))
        for i, a in enumerate(self._aylar):
            cx = sol + grup_w * i + grup_w / 2
            vals = (a.satis, a.brut, a.nakit_net)
            for j, v in enumerate(vals):
                bx = cx + (j - 1) * (bar_w + 2) - bar_w / 2
                vy = y_of(v)
                top = min(vy, zy)
                bh = abs(vy - zy)
                p.fillRect(QRectF(bx, top, bar_w, max(1.0, bh)), renkler[j])
            p.setPen(QPen(QColor(MUTED)))
            ay_kisa = a.ay[2:] if len(a.ay) >= 7 else a.ay
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _oranlar_panel(tr: TrendRapor) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(16)
    g.setVerticalSpacing(10)
    g.setColumnStretch(2, 1)

    for r, o in enumerate(tr.oranlar):
        g.addWidget(_satir_label(o.ad, bold=True), r, 0)
        deger = o.metin()
        renk = "#374151"
        if o.deger is not None and o.kod in ("cari", "asit", "nakit_oran"):
            renk = POZ if o.deger >= 1.0 else NEG
        elif o.deger is not None and o.kod == "borc_oz":
            renk = NEG if o.deger > 2.0 else POZ
        g.addWidget(_satir_label(deger, bold=True, renk=renk, sag=True), r, 1)
        acik = _satir_label(o.aciklama, renk=FAINT, boyut=11)
        acik.setWordWrap(True)
        g.addWidget(acik, r, 2)
    if not tr.oranlar:
        g.addWidget(_satir_label("Bilanço verisi yok — oran hesaplanamadı.", renk=FAINT), 0, 0, 1, 3)
    return _card("FİNANSAL ORANLAR  (bilanço)", inner)


def _bilanco_ozet(tr: TrendRapor) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(7)

    def satir(r: int, ad: str, deger: str, *, bold: bool = False) -> None:
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, sag=True), r, 1)

    satir(0, "Dönen varlıklar", tl(tr.donen))
    satir(1, "KVYK", tl(tr.kvyk))
    satir(2, "Özkaynak", tl(tr.ozkaynak), bold=True)
    satir(3, "Nakit", tl(tr.nakit))
    satir(4, "Alacak", tl(tr.alacak))
    satir(5, "Stok", tl(tr.stok))
    return _card("BİLANÇO ÖZETİ", inner)


def _trend_panel(tr: TrendRapor) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:{ACCENT};'>■</span> Satış &nbsp;&nbsp;"
        f"<span style='color:{POZ};'>■</span> Brüt Kâr &nbsp;&nbsp;"
        "<span style='color:#d97706;'>■</span> Net Nakit"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TrendChart(tr))
    return _card("AYLIK TREND  (stok + banka)", inner)


def build_trend_widget(tr: TrendRapor, firma: str = "") -> QWidget:
    content = QWidget()
    content.setObjectName("trContent")
    content.setStyleSheet("QWidget#trContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>TREND &amp; ORANLAR &nbsp;·&nbsp; "
        f"{tr.bas} → {tr.bit}{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Aylık fiili satış/alış/nakit trendi ile "
        f"bilanço tarihindeki klasik finansal oranlar.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, tr.bit))

    # Hero KPI şeridi
    hero = QFrame()
    hero.setObjectName("trHero")
    hero.setStyleSheet(
        f"QFrame#trHero {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 14px; }}"
    )
    hl = QHBoxLayout(hero)
    hl.setContentsMargins(20, 16, 20, 16)
    hl.setSpacing(24)
    cari = next((o for o in tr.oranlar if o.kod == "cari"), None)
    for baslik, deger, vr in (
        ("TOPLAM SATIŞ", tl(tr.toplam_satis), "#0f172a"),
        ("TOPLAM BRÜT", tl(tr.toplam_brut), _renk(tr.toplam_brut)),
        ("NAKİT NET", tl(tr.toplam_nakit_net), _renk(tr.toplam_nakit_net)),
        ("CARİ ORAN", cari.metin() if cari else "—",
         (POZ if cari and cari.deger is not None and cari.deger >= 1 else NEG)
         if cari and cari.deger is not None else MUTED),
    ):
        col = QVBoxLayout()
        col.setSpacing(2)
        lb = QLabel(baslik)
        lb.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
        col.addWidget(lb)
        dv = QLabel(deger)
        dv.setStyleSheet(f"color: {vr}; font-size: 18px; font-weight: 800;")
        col.addWidget(dv)
        hl.addLayout(col, 1)
    root.addWidget(hero)

    row = QHBoxLayout()
    row.setSpacing(20)
    row.addWidget(_oranlar_panel(tr), 2)
    row.addWidget(_bilanco_ozet(tr), 1)
    root.addLayout(row)
    root.addWidget(_trend_panel(tr))
    root.addStretch(1)
    return content
