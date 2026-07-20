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
from domain.runway import RunwayTakvim
from domain.tahmin import Tahmin
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from ui.gercek_durum_view import NEG, POZ, _card, _renk, _satir_label
from ui.styles import PRIMARY_SOFT

_AY_KISA = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
            "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")


def _ay_str(yyyymm: str) -> str:
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
        return f"{_AY_KISA[m - 1]} {y}"
    except (ValueError, IndexError):
        return yyyymm


def _runway_banner_takvim(rt: RunwayTakvim) -> QFrame:
    """Vade-takvimli runway özeti (gerçek açık kalemlere dayanır)."""
    if rt.tukenme_ay is not None:
        renk, bg, kenar = NEG, "#fdecec", "#f3b4b4"
        baslik = f"Nakit {_ay_str(rt.tukenme_ay)} ayında eksiye düşüyor"
        oneri = "→ Tahsilatı öne çek, ödemeleri ertele; kısa vadeli finansman planla."
    elif rt.gider_eksik:
        # Gider okunamadıysa "sağlıklı" demek yanıltıcı — sarı, uyarılı.
        renk, bg, kenar = "#b45309", "#fdf3e0", "#f0d090"
        baslik = "Runway giderleri eksik — sonuç güvenilir değil"
        oneri = ""
    else:
        renk, bg, kenar = "#15803d", "#e8f6ee", "#bfe3cd"
        baslik = (f"Nakit {rt.ufuk_ay} ay boyunca pozitif "
                  f"(en düşük {tl(rt.en_dusuk_nakit)} · {_ay_str(rt.en_dusuk_ay)})")
        oneri = ""
    card = QFrame()
    card.setObjectName("rwBanner")
    card.setStyleSheet(
        f"QFrame#rwBanner {{ background: {bg}; border: 1px solid {kenar}; border-radius: 12px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 12, 18, 12)
    lay.setSpacing(2)
    eyebrow = QLabel("NAKİT RUNWAY  ·  vade takvimi")
    eyebrow.setStyleSheet(
        f"color: {renk}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; "
        "background: transparent;"
    )
    lay.addWidget(eyebrow)
    bl = QLabel(baslik)
    bl.setWordWrap(True)
    bl.setStyleSheet(f"color: {renk}; font-size: 18px; font-weight: 800; background: transparent;")
    lay.addWidget(bl)
    kredi = f"  ·  aylık kredi {tl(rt.aylik_kredi)}" if rt.aylik_kredi > 0.005 else ""
    sub = QLabel(
        f"Mevcut nakit {tl(rt.baslangic_nakit)}  ·  aylık düzenli gider "
        f"{tl(rt.aylik_gider)}{kredi}" + (f"   {oneri}" if oneri else "")
    )
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
    lay.addWidget(sub)
    if rt.gider_eksik:
        uy = QLabel(
            "⚠ Maaş / genel gider / kredi ödemeleri Mikro'dan kategorize edilemedi "
            "(aylık düzenli gider 0 okundu). Bu yüzden runway giderleri EKSİK ve "
            "gerçek durumdan iyimserdir — bu haliyle nakit krizini göremeyebilir."
        )
        uy.setWordWrap(True)
        uy.setStyleSheet("color: #8a5a00; font-size: 11.5px; font-weight: 600; background: transparent;")
        lay.addWidget(uy)
    return card


def _runway_tablo_takvim(rt: RunwayTakvim) -> QFrame:
    """Ay-ay nakit takvimi: girecek − çıkacak → kümülatif nakit."""
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(7)
    g.setColumnStretch(0, 1)
    for c, bs in ((1, "Girecek"), (2, "Çıkacak"), (3, "Net"), (4, "Nakit")):
        g.addWidget(_satir_label(bs, renk=MUTED, boyut=11, bold=True, sag=True), 0, c)
    for i, a in enumerate(rt.aylar, start=1):
        g.addWidget(_satir_label(_ay_str(a.ay), bold=True), i, 0)
        g.addWidget(_satir_label(tl(a.giren) if a.giren > 0.005 else "—", sag=True,
                                 renk=POZ if a.giren > 0.005 else FAINT), i, 1)
        g.addWidget(_satir_label(tl(a.cikan) if a.cikan > 0.005 else "—", sag=True,
                                 renk=NEG if a.cikan > 0.005 else FAINT), i, 2)
        g.addWidget(_satir_label(("+" if a.net >= 0 else "") + tl(a.net), sag=True,
                                 renk=_renk(a.net)), i, 3)
        g.addWidget(_satir_label(tl(a.nakit), sag=True, bold=True, renk=_renk(a.nakit)), i, 4)
    not_lbl = _satir_label(
        "Konservatif taban senaryo: eldeki açık alacak/borç vadeleri + düzenli aylık giderler. "
        "Yeni satış varsayılmaz — gerçek nakit büyük ihtimalle bundan daha iyi olur.",
        renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, len(rt.aylar) + 1, 0, 1, 5)
    return _card("NAKİT TAKVİMİ  (ay-ay, vadeye göre)", inner)


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


def build_tahmin_widget(
    t: Tahmin, firma: str = "", runway: RunwayTakvim | None = None,
) -> QWidget:
    """Bir Tahmin'den projeksiyon görünümü üretir; runway verilirse üstte gösterir."""
    content = QWidget()
    content.setObjectName("tahminContent")
    content.setStyleSheet("QWidget#tahminContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    # Gerçek (vade-takvimli) runway — headline. Düzenlenebilir senaryo altta.
    if runway is not None and runway.aylar:
        root.addWidget(_runway_banner_takvim(runway))
        root.addWidget(_runway_tablo_takvim(runway))
        ayirac = QLabel("WHAT-IF SENARYO  ·  düzenlenebilir varsayımlar")
        ayirac.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; "
            "background: transparent; margin-top: 4px;")
        root.addWidget(ayirac)

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
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, v.baslangic_ay))

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
