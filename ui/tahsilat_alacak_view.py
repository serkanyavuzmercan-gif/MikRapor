"""
Alacak & Borç — yerel Qt görünümü.

Cari hareketlerden (resmi GL'ye dokunmadan) alacak/borç yaşlandırması, ileriye dönük net vade
takvimi ve dönem tahsilat/ödeme performansını gösterir. Görünüm yardımcıları Nakit & Kârlılık
sekmesiyle paylaşılır (tek tip kart/satır stili).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.tahsilat_alacak import AGING_KOVALAR, VADE_KOVALAR, TahsilatAlacak
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height, _kpi_card
from ui.gercek_durum_view import (
    _DARK,
    NEG,
    POZ,
    _agac,
    _c,
    _card,
    _ic,
    _renk,
    _tsatir,
)
from ui.styles import PRIMARY_SOFT

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
    # col0 etiket + col1 çubuk (esner) + col2 tutar; hover + zebra ağaçtan gelir.
    t = _agac(3, [(0, 138), (2, 130)], esnek=1)
    enb = max((aging.get(k, 0.0) for k in AGING_KOVALAR), default=0.0) or 1.0
    for k in AGING_KOVALAR:
        v = aging.get(k, 0.0)
        renk = _AGING_RENK[k]
        it = _tsatir(t, [_c(k), _c(""),
                         _c(tl(v), renk=renk if v > 0.005 else FAINT, kalin=v > 0.005, sag=True)])
        t.setItemWidget(it, 1, _oran_bar(v / enb, renk))
    _tsatir(t, [_c("Toplam", kalin=True), _c(""), _c(tl(toplam), kalin=True, sag=True)])
    _fit_height(t)

    notlar: list[tuple[str, str]] = []
    if gecikmis > 0.005:
        oran = gecikmis / toplam * 100 if toplam > 0.005 else 0.0
        notlar.append((f"Gecikmiş: {tl(gecikmis)}  (%{oran:.0f})", NEG))
    return _card(baslik, _ic(t, notlar))


def _performans_panel(ta: TahsilatAlacak) -> QFrame:
    def gun(v):
        return "—" if v is None else f"{v:.0f} gün"

    def pct(v):
        return "—" if v is None else ("%" + f"{v:.0f}")

    t = _agac(2, [(1, 130)])
    _tsatir(t, [_c("Dönem Tahsilatı (müşteriden)"), _c(tl(ta.donem_tahsilat), renk=POZ, sag=True)])
    _tsatir(t, [_c("Dönem Kredili Satış (KDV dahil)"), _c(tl(ta.donem_satis), sag=True)])
    _tsatir(t, [_c("Tahsilat Oranı", kalin=True),
                _c(pct(ta.tahsilat_orani), renk=_renk((ta.tahsilat_orani or 0) - 100),
                   kalin=True, sag=True)])
    _tsatir(t, [_c("Ort. Tahsilat Süresi (DSO)", kalin=True), _c(gun(ta.dso), kalin=True, sag=True)])
    _tsatir(t, [_c("Dönem Ödemesi (satıcıya)"), _c(tl(ta.donem_odeme), renk=NEG, sag=True)])
    _tsatir(t, [_c("Dönem Alış (KDV dahil)"), _c(tl(ta.donem_alis), sag=True)])
    _tsatir(t, [_c("Ort. Ödeme Süresi (DPO)", kalin=True), _c(gun(ta.dpo), kalin=True, sag=True)])
    _fit_height(t)

    notlar: list[tuple[str, str]] = []
    if ta.dso is not None and ta.dpo is not None:
        fark = ta.dpo - ta.dso
        notlar.append((
            f"Nakit döngüsü: tahsilat {ta.dso:.0f}g, ödeme {ta.dpo:.0f}g — "
            + ("satıcı bizi finanse ediyor." if fark >= 0 else "biz satıcıyı finanse ediyoruz."),
            FAINT))
    notlar.append((
        "Cari kaynaklı tutarlar KDV dahildir; Gelir/Nakit tabındaki net satıştan (KDV hariç) "
        "farklı çıkar. Oranlar (DSO, tahsilat) KDV'den etkilenmez.", FAINT))
    return _card("TAHSİLAT & ÖDEME PERFORMANSI  (dönem)", _ic(t, notlar))


def _vade_takvimi_panel(ta: TahsilatAlacak) -> QFrame:
    t = _agac(4, [(1, 116), (2, 116), (3, 120)])
    _tsatir(t, [_c(""), _c("Girecek", renk=MUTED, kalin=True, sag=True),
                _c("Çıkacak", renk=MUTED, kalin=True, sag=True),
                _c("Net", renk=MUTED, kalin=True, sag=True)])
    nv = ta.net_vade()
    for k in VADE_KOVALAR:
        a = ta.alacak_vade.get(k, 0.0)
        b = ta.borc_vade.get(k, 0.0)
        n = nv.get(k, 0.0)
        bold = k == VADE_KOVALAR[0]  # Gecikmiş vurgulu
        _tsatir(t, [_c(k, kalin=bold, renk=NEG if bold else _DARK),
                    _c(tl(a) if a > 0.005 else "—", renk=POZ if a > 0.005 else FAINT, sag=True),
                    _c(tl(b) if b > 0.005 else "—", renk=NEG if b > 0.005 else FAINT, sag=True),
                    _c(("+" if n >= 0 else "") + tl(n), renk=_renk(n), kalin=True, sag=True)])
    _fit_height(t)

    notlar = [("Açık alacak/borçların vade tarihine göre beklenen nakit hareketi. «Gecikmiş» = "
               "vadesi geçmiş; normalde çoktan tahsil/ödeme edilmiş olmalı.", FAINT)]
    return _card("NET VADE TAKVİMİ  (ileriye dönük)", _ic(t, notlar))


def _top_panel(baslik: str, kayitlar: list, renk: str) -> QFrame:
    t = _agac(3, [(1, 120), (2, 135)])
    if not kayitlar:
        _tsatir(t, [_c("Kayıt yok.", renk=FAINT), _c(""), _c("")])
        _fit_height(t)
        return _card(baslik, _ic(t))
    for c in kayitlar:
        ad = (c.unvan or c.kod)[:38]
        gec = f"gecikmiş {tl(c.gecikmis)}" if c.gecikmis > 0.005 else ""
        _tsatir(t, [_c(ad), _c(tl(c.net), renk=renk, kalin=True, sag=True),
                    _c(gec, renk=NEG, sag=True)])
    _fit_height(t)
    return _card(baslik, _ic(t))


def build_tahsilat_alacak_widget(ta: TahsilatAlacak, firma: str = "") -> QWidget:
    """Bir TahsilatAlacak'tan QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("taContent")
    content.setStyleSheet("QWidget#taContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    kaynak = {
        "vade": "vade tarihi",
        "plan": "ödeme planı vadesi (evrak tarihi + cari vade günü)",
        "tarih": "hareket tarihi (vade bilgisi yok)",
    }.get(ta.vade_kaynagi, "vade tarihi")
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>ALACAK &amp; BORÇ &nbsp;·&nbsp; "
        f"{ta.bit} itibarıyla{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Cari hareketlerden — açık alacak/borç "
        f"{kaynak}na göre yaşlandırılır; dönem ({ta.bas} → {ta.bit}) tahsilat/ödeme performansı "
        f"ve ileriye dönük net nakit takvimi.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, ta.bit, kaynak="canli"))

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
    kpi.addWidget(_kpi_card("TOPLAM ALACAK", tl(ta.alacak_toplam), PRIMARY_SOFT, ACCENT))
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
    row3.addWidget(_top_panel("EN ÇOK ALACAKLI OLDUĞUMUZ MÜŞTERİLER", ta.top_alacak, ACCENT), 1)
    row3.addWidget(_top_panel("EN ÇOK BORÇLU OLDUĞUMUZ SATICILAR", ta.top_borc, "#b45309"), 1)
    root.addLayout(row3)
    root.addStretch(1)
    return content
