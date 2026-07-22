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
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.terimler import sade_oran
from domain.trend import TrendRapor
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height
from ui.gercek_durum_view import _DARK, _agac, _c, _ic, _tsatir
from ui.nav_tip import bagla_nav_tip
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
    t = _agac(3, [(0, 190), (1, 95)], esnek=2)
    if not tr.oranlar:
        _tsatir(t, [_c("Bilanço verisi yok — oran hesaplanamadı.", renk=FAINT), _c(""), _c("")])
        _fit_height(t)
        return _card("FİNANSAL ORANLAR  (bilanço)", _ic(t))
    for o in tr.oranlar:
        renk = _DARK
        if o.deger is not None and o.kod in ("cari", "asit", "nakit_oran"):
            renk = POZ if o.deger >= 1.0 else NEG
        elif o.deger is not None and o.kod == "borc_oz":
            renk = NEG if o.deger > 2.0 else POZ
        _tsatir(t, [_c(o.ad, kalin=True), _c(o.metin(), renk=renk, kalin=True, sag=True),
                    _c(o.aciklama, renk=FAINT)])
    _fit_height(t)
    return _card("FİNANSAL ORANLAR  (bilanço)", _ic(t))


def _bilanco_ozet(tr: TrendRapor) -> QFrame:
    t = _agac(2, [(1, 130)])
    _tsatir(t, [_c("Dönen varlıklar"), _c(tl(tr.donen), sag=True)])
    _tsatir(t, [_c("KVYK"), _c(tl(tr.kvyk), sag=True)])
    _tsatir(t, [_c("Özkaynak", kalin=True), _c(tl(tr.ozkaynak), kalin=True, sag=True)])
    _tsatir(t, [_c("Nakit"), _c(tl(tr.nakit), sag=True)])
    _tsatir(t, [_c("Alacak"), _c(tl(tr.alacak), sag=True)])
    _tsatir(t, [_c("Stok"), _c(tl(tr.stok), sag=True)])
    _fit_height(t)
    return _card("BİLANÇO ÖZETİ", _ic(t))


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
    root.addWidget(baslik_ile_gelecek_uyari(head, tr.bit, kaynak="canli"))

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
    for baslik, deger, vr, ipucu in (
        ("TOPLAM SATIŞ", tl(tr.toplam_satis), "#0f172a", ""),
        ("TOPLAM BRÜT", tl(tr.toplam_brut), _renk(tr.toplam_brut), ""),
        ("NAKİT NET", tl(tr.toplam_nakit_net), _renk(tr.toplam_nakit_net), ""),
        ("CARİ ORAN", cari.metin() if cari else "—",
         (POZ if cari and cari.deger is not None and cari.deger >= 1 else NEG)
         if cari and cari.deger is not None else MUTED,
         sade_oran("cari")),
    ):
        col = QVBoxLayout()
        col.setSpacing(2)
        # Açıklamasız KPI'ya hover'da sade açıklama (?) balonu bağlanır.
        lb = QLabel(baslik + ("  ⓘ" if ipucu else ""))
        lb.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
        if ipucu:
            bagla_nav_tip(lb, ipucu, eyebrow="TERİM")
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
