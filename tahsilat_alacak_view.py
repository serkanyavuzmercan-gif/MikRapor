"""
Tahsilat & Alacak — yerel Qt görünümü.

Cari hareketlerden (resmi GL'ye dokunmadan) alacak/borç yaşlandırması, ileriye dönük net vade
takvimi ve dönem tahsilat/ödeme performansını gösterir. Görünüm yardımcıları Nakit & Kârlılık
sekmesiyle paylaşılır (tek tip kart/satır stili).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from gercek_durum_view import NEG, POZ, _card, _cizgi, _renk, _satir_label
from mizan_bilanco import tl
from tahsilat_alacak import AGING_KOVALAR, VADE_KOVALAR, TahsilatAlacak

# Yaşlandırma kovası → renk (vadesi gelmemiş yeşil → 90+ kırmızı)
_AGING_RENK = {
    AGING_KOVALAR[0]: "#15803d",
    AGING_KOVALAR[1]: "#65a30d",
    AGING_KOVALAR[2]: "#d97706",
    AGING_KOVALAR[3]: "#ea580c",
    AGING_KOVALAR[4]: "#b91c1c",
}


def _oran_bar(oran: float, renk: str) -> QWidget:
    """0..1 oranında dolu, ince yatay bar (QPainter'sız — stretch ile)."""
    w = QWidget()
    w.setFixedHeight(8)
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    dolu = QFrame()
    dolu.setStyleSheet(f"background: {renk}; border-radius: 4px;")
    bos = QFrame()
    bos.setStyleSheet("background: #e8edf3; border-radius: 4px;")
    oran = max(0.0, min(1.0, oran))
    lay.addWidget(dolu, max(1, int(oran * 1000)))
    lay.addWidget(bos, max(1, int((1.0 - oran) * 1000)))
    return w


def _yaslandirma_panel(baslik: str, aging: dict, toplam: float, gecikmis: float) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(9)
    g.setColumnStretch(1, 1)

    enb = max((aging.get(k, 0.0) for k in AGING_KOVALAR), default=0.0) or 1.0
    r = 0
    for k in AGING_KOVALAR:
        v = aging.get(k, 0.0)
        renk = _AGING_RENK[k]
        g.addWidget(_satir_label(k, renk="#374151"), r, 0)
        g.addWidget(_oran_bar(v / enb, renk), r, 1)
        g.addWidget(_satir_label(tl(v), sag=True, bold=v > 0.005,
                                 renk=renk if v > 0.005 else FAINT), r, 2)
        r += 1
    g.addWidget(_cizgi(), r, 0, 1, 3)
    r += 1
    g.addWidget(_satir_label("Toplam", bold=True), r, 0)
    g.addWidget(_satir_label(tl(toplam), sag=True, bold=True), r, 2)
    r += 1
    if gecikmis > 0.005:
        oran = gecikmis / toplam * 100 if toplam > 0.005 else 0.0
        g.addWidget(_satir_label(
            f"Gecikmiş: {tl(gecikmis)}  (%{oran:.0f})", renk=NEG, boyut=11), r, 0, 1, 3)
    return _card(baslik, inner)


def _performans_panel(ta: TahsilatAlacak) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    def satir(r: int, ad: str, deger: str, *, bold: bool = False, renk: str = "#374151") -> None:
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, renk=renk, sag=True), r, 1)

    def gun(v):
        return "—" if v is None else f"{v:.0f} gün"

    def pct(v):
        return "—" if v is None else ("%" + f"{v:.0f}")

    satir(0, "Dönem Tahsilatı (müşteriden)", tl(ta.donem_tahsilat), renk=POZ)
    satir(1, "Dönem Kredili Satış", tl(ta.donem_satis))
    satir(2, "Tahsilat Oranı", pct(ta.tahsilat_orani), bold=True,
          renk=_renk((ta.tahsilat_orani or 0) - 100))
    satir(3, "Ort. Tahsilat Süresi (DSO)", gun(ta.dso), bold=True)
    g.addWidget(_cizgi(), 4, 0, 1, 2)
    satir(5, "Dönem Ödemesi (satıcıya)", tl(ta.donem_odeme), renk=NEG)
    satir(6, "Dönem Alış", tl(ta.donem_alis))
    satir(7, "Ort. Ödeme Süresi (DPO)", gun(ta.dpo), bold=True)
    if ta.dso is not None and ta.dpo is not None:
        fark = ta.dpo - ta.dso
        g.addWidget(_satir_label(
            f"Nakit döngüsü: tahsilat {ta.dso:.0f}g, ödeme {ta.dpo:.0f}g — "
            + ("satıcı bizi finanse ediyor." if fark >= 0 else "biz satıcıyı finanse ediyoruz."),
            renk=FAINT, boyut=11), 8, 0, 1, 2)
    return _card("TAHSİLAT & ÖDEME PERFORMANSI  (dönem)", inner)


def _vade_takvimi_panel(ta: TahsilatAlacak) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    for c, b in ((1, "Girecek"), (2, "Çıkacak"), (3, "Net")):
        g.addWidget(_satir_label(b, renk=MUTED, boyut=11, bold=True, sag=True), 0, c)

    nv = ta.net_vade()
    r = 1
    for k in VADE_KOVALAR:
        a = ta.alacak_vade.get(k, 0.0)
        b = ta.borc_vade.get(k, 0.0)
        n = nv.get(k, 0.0)
        bold = k == VADE_KOVALAR[0]  # Gecikmiş vurgulu
        g.addWidget(_satir_label(k, bold=bold,
                                 renk=NEG if bold else "#374151"), r, 0)
        g.addWidget(_satir_label(tl(a) if a > 0.005 else "—", sag=True,
                                 renk=POZ if a > 0.005 else FAINT), r, 1)
        g.addWidget(_satir_label(tl(b) if b > 0.005 else "—", sag=True,
                                 renk=NEG if b > 0.005 else FAINT), r, 2)
        g.addWidget(_satir_label(("+" if n >= 0 else "") + tl(n), sag=True, bold=True,
                                 renk=_renk(n)), r, 3)
        r += 1
    not_lbl = _satir_label(
        "Açık alacak/borçların vade tarihine göre beklenen nakit hareketi. «Gecikmiş» = vadesi "
        "geçmiş; normalde çoktan tahsil/ödeme edilmiş olmalı.", renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, r, 0, 1, 4)
    return _card("NET VADE TAKVİMİ  (ileriye dönük)", inner)


def _top_panel(baslik: str, kayitlar: list, renk: str) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(7)
    g.setColumnStretch(0, 1)
    if not kayitlar:
        g.addWidget(_satir_label("Kayıt yok.", renk=FAINT), 0, 0)
        return _card(baslik, inner)
    r = 0
    for c in kayitlar:
        ad = (c.unvan or c.kod)[:38]
        g.addWidget(_satir_label(ad, renk="#374151"), r, 0)
        g.addWidget(_satir_label(tl(c.net), sag=True, bold=True, renk=renk), r, 1)
        if c.gecikmis > 0.005:
            g.addWidget(_satir_label(f"gecikmiş {tl(c.gecikmis)}", renk=NEG, boyut=10, sag=True),
                        r, 2)
        r += 1
    return _card(baslik, inner)


def build_tahsilat_alacak_widget(ta: TahsilatAlacak, firma: str = "") -> QWidget:
    """Bir TahsilatAlacak'tan QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("taContent")
    content.setStyleSheet("QWidget#taContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(24, 18, 24, 24)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    kaynak = {
        "vade": "vade tarihi",
        "plan": "ödeme planı vadesi (evrak tarihi + cari vade günü)",
        "tarih": "hareket tarihi (vade bilgisi yok)",
    }.get(ta.vade_kaynagi, "vade tarihi")
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>TAHSİLAT &amp; ALACAK &nbsp;·&nbsp; "
        f"{ta.bit} itibarıyla{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Cari hareketlerden — açık alacak/borç "
        f"{kaynak}na göre yaşlandırılır; dönem ({ta.bas} → {ta.bit}) tahsilat/ödeme performansı "
        f"ve ileriye dönük net nakit takvimi.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    if ta.cari_sayisi == 0:
        uyari = QLabel(
            "⚠ <b>Bu tarihte açık cari bakiye bulunamadı.</b> Mikro'da veri olan dönemi/yılı seçin; "
            "«Mikro Ayarları»'ndaki çalışma yılı ile bitiş tarihi uyumlu olmalı."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdf3e0; border: 1px solid #f0d090; border-radius: 8px; "
            "color: #8a5a00; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("TOPLAM ALACAK", tl(ta.alacak_toplam), "#eef4ff", "#1d4ed8"))
    ag_bg, ag_vr = ("#fdecec", NEG) if ta.alacak_gecikmis > 0.005 else ("#e8f6ee", POZ)
    kpi.addWidget(_kpi_card("GECİKMİŞ ALACAK", tl(ta.alacak_gecikmis), ag_bg, ag_vr))
    kpi.addWidget(_kpi_card("TOPLAM BORÇ", tl(ta.borc_toplam), "#fdf3e0", "#b45309"))
    np_bg, np_vr = ("#e8f6ee", POZ) if ta.net_pozisyon >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("NET POZİSYON  (alacak−borç)", tl(ta.net_pozisyon), np_bg, np_vr))
    root.addLayout(kpi)

    row1 = QHBoxLayout()
    row1.setSpacing(20)
    row1.addWidget(_yaslandirma_panel(
        "ALACAK YAŞLANDIRMA  (müşteri)", ta.alacak_aging, ta.alacak_toplam, ta.alacak_gecikmis), 1)
    row1.addWidget(_yaslandirma_panel(
        "BORÇ YAŞLANDIRMA  (satıcı)", ta.borc_aging, ta.borc_toplam, ta.borc_gecikmis), 1)
    root.addLayout(row1)

    row2 = QHBoxLayout()
    row2.setSpacing(20)
    row2.addWidget(_performans_panel(ta), 1)
    row2.addWidget(_vade_takvimi_panel(ta), 1)
    root.addLayout(row2)

    row3 = QHBoxLayout()
    row3.setSpacing(20)
    row3.addWidget(_top_panel("EN ÇOK ALACAKLI OLDUĞUMUZ MÜŞTERİLER", ta.top_alacak, "#1d4ed8"), 1)
    row3.addWidget(_top_panel("EN ÇOK BORÇLU OLDUĞUMUZ SATICILAR", ta.top_borc, "#b45309"), 1)
    root.addLayout(row3)
    root.addStretch(1)
    return content
