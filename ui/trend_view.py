"""
Mukayese & Oranlar — yerel Qt görünümü.

Aylık satış/alış/brüt/nakit trend grafiği + bilançodan türetilen finansal oranlar.
Grafik ek bağımlılık olmadan QPainter ile çizilir (Nakit & Kârlılık ile aynı dil).
"""

from __future__ import annotations

import math

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
from domain.trend import MALIYET_EKSIK_UYARI, TrendRapor
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height
from ui.gercek_durum_view import _DARK, _agac, _c, _ic, _tsatir
from ui.mukayese_view import mukayese_karti
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


_AY_KISA = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
            "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")

# Çubuklar SATIŞ ve ALIŞ: aradaki fark zaten brüt kârdır, gözle okunur. Brüt kârı
# ayrı çubuk yapmak hem yer kaplıyor hem de satışın içinden çıktığı için mükerrer
# görünüyordu. Nakit ayrı renkte ve ÇİZGİ — farklı bir büyüklük olduğu anlaşılsın.
_C_SATIS = "#0f766e"
_C_ALIS = "#5eead4"
_C_NAKIT = "#d97706"


def _ay_etiket(yyyymm: str) -> str:
    """'2026-01' → 'Oca 26' (grafik ekseni için kısa Türkçe)."""
    try:
        return f"{_AY_KISA[int(yyyymm[5:7]) - 1]} {yyyymm[2:4]}"
    except (ValueError, IndexError):
        return yyyymm


def _kisa_tutar(v: float) -> str:
    """Eksen etiketi: 5.923.722 → '5,9M' · 356.949 → '357B' · 0 → '0'."""
    m = abs(v)
    if m < 1000:
        return f"{v:,.0f}".replace(",", ".")
    if m < 1_000_000:
        return f"{v / 1000:,.0f}".replace(",", ".") + "B"
    return f"{v / 1_000_000:.1f}".replace(".", ",") + "M"


def _guzel_adim(aralik: float, hedef_bolme: int = 4) -> float:
    """Eksen için yuvarlak bir adım seçer (1/2/2,5/5 × 10ⁿ) — etiketler okunur olsun."""
    if aralik <= 0:
        return 1.0
    ham = aralik / max(1, hedef_bolme)
    us = 10.0 ** math.floor(math.log10(ham))
    for k in (1.0, 2.0, 2.5, 5.0, 10.0):
        if ham <= k * us:
            return k * us
    return 10.0 * us


class _TrendChart(QWidget):
    """Aylık Satış / Alış (çubuk) + Net Nakit (çizgi) — ölçekli eksen, hover değer."""

    def __init__(self, aylar: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._aylar = aylar
        self._vurgu = -1
        self.setMinimumHeight(250)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

    # ---------------------------------------------------------------- geometri
    def _cerceve(self) -> tuple[float, float, float, float]:
        return 58.0, 12.0, 16.0, 30.0  # sol (eksen etiketi) · sağ · üst · alt

    def _grup_genislik(self) -> float:
        sol, sag, _, _ = self._cerceve()
        return max(1.0, (self.width() - sol - sag) / max(1, len(self._aylar)))

    def _ay_indeksi(self, x: float) -> int:
        sol, _, _, _ = self._cerceve()
        i = int((x - sol) // self._grup_genislik())
        return i if 0 <= i < len(self._aylar) else -1

    # ------------------------------------------------------------------ olaylar
    def mouseMoveEvent(self, ev) -> None:  # noqa: N802 — Qt API
        i = self._ay_indeksi(ev.position().x())
        if i != self._vurgu:
            self._vurgu = i
            self.update()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802 — Qt API
        if self._vurgu != -1:
            self._vurgu = -1
            self.update()
        super().leaveEvent(ev)

    # ------------------------------------------------------------------- çizim
    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        sol, sag, ust, alt = self._cerceve()
        cw, ch = w - sol - sag, h - ust - alt
        if not self._aylar or cw <= 0 or ch <= 0:
            p.setPen(QPen(QColor(FAINT)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Trend için veri yok")
            p.end()
            return

        degerler = [v for a in self._aylar for v in (a.satis, a.alis, a.nakit_net)]
        adim = _guzel_adim(max(degerler + [0.0]) - min(degerler + [0.0]))
        max_v = math.ceil(max(degerler + [0.0]) / adim) * adim
        min_v = math.floor(min(degerler + [0.0]) / adim) * adim
        span = (max_v - min_v) or adim

        def y_of(v: float) -> float:
            return ust + ch * ((max_v - v) / span)

        # ---- ızgara + eksen etiketleri (büyüklük okunabilsin)
        p.setFont(QFont("Segoe UI", 7))
        cizgi = math.floor(min_v / adim)
        while cizgi * adim <= max_v + 1e-6:
            v = cizgi * adim
            y = y_of(v)
            sifir = abs(v) < 1e-6
            p.setPen(QPen(QColor("#cbd5e1" if sifir else "#eef2f7"), 1,
                          Qt.PenStyle.DashLine if sifir else Qt.PenStyle.SolidLine))
            p.drawLine(int(sol), int(y), int(sol + cw), int(y))
            p.setPen(QPen(QColor(MUTED if sifir else FAINT)))
            p.drawText(QRectF(0, y - 8, sol - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       _kisa_tutar(v))
            cizgi += 1

        grup_w = self._grup_genislik()
        bar_w = min(20.0, grup_w / 3.4)
        zy = y_of(0.0)

        # ---- vurgulanan ay şeridi (hover)
        if 0 <= self._vurgu < len(self._aylar):
            p.fillRect(QRectF(sol + grup_w * self._vurgu, ust, grup_w, ch),
                       QColor("#0f766e14"))

        # ---- çubuklar: satış + alış (aradaki boşluk = brüt kâr)
        for i, a in enumerate(self._aylar):
            cx = sol + grup_w * i + grup_w / 2
            for j, (v, renk) in enumerate(((a.satis, _C_SATIS), (a.alis, _C_ALIS))):
                bx = cx + (j - 1) * (bar_w + 2) + 1
                vy = y_of(v)
                p.fillRect(QRectF(bx, min(vy, zy), bar_w, max(1.0, abs(vy - zy))),
                           QColor(renk))

        # ---- nakit: çizgi + nokta (çubuk değil — farklı bir büyüklük)
        noktalar = [(sol + grup_w * i + grup_w / 2, y_of(a.nakit_net))
                    for i, a in enumerate(self._aylar)]
        p.setPen(QPen(QColor(_C_NAKIT), 2))
        for i in range(1, len(noktalar)):
            p.drawLine(int(noktalar[i - 1][0]), int(noktalar[i - 1][1]),
                       int(noktalar[i][0]), int(noktalar[i][1]))
        p.setBrush(QColor(_C_NAKIT))
        for x, y in noktalar:
            p.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # ---- ay etiketleri (kalabalıksa seyreltilir)
        atla = max(1, int(len(self._aylar) / max(1, cw // 52)))
        p.setPen(QPen(QColor(MUTED)))
        for i, a in enumerate(self._aylar):
            if i % atla and i != len(self._aylar) - 1:
                continue
            p.drawText(QRectF(sol + grup_w * i, h - alt + 6, grup_w, alt - 8),
                       Qt.AlignmentFlag.AlignCenter, _ay_etiket(a.ay))

        # ---- hover kutusu: o ayın üç değeri
        if 0 <= self._vurgu < len(self._aylar):
            self._kutu_ciz(p, self._aylar[self._vurgu], sol, ust, cw, grup_w)
        p.end()

    def _kutu_ciz(self, p: QPainter, a, sol: float, ust: float,
                  cw: float, grup_w: float) -> None:
        satirlar = ((("Satış"), tl(a.satis), _C_SATIS),
                    ("Alış", tl(a.alis), "#0d9488"),
                    ("Brüt kâr", tl(a.brut), "#0d9488"),
                    ("Net nakit", tl(a.nakit_net), _C_NAKIT))
        p.setFont(QFont("Segoe UI", 7))
        fm = p.fontMetrics()
        kw = max(fm.horizontalAdvance(f"{ad}  {deg}") for ad, deg, _ in satirlar) + 22
        kh = 14 * len(satirlar) + 22
        kx = sol + grup_w * self._vurgu + grup_w / 2 + 10
        if kx + kw > sol + cw:
            kx = sol + grup_w * self._vurgu + grup_w / 2 - kw - 10
        ky = ust + 6
        p.setPen(QPen(QColor("#cbd5e1")))
        p.setBrush(QColor("#ffffffee"))
        p.drawRoundedRect(QRectF(kx, ky, kw, kh), 6, 6)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(_DARK)))
        p.drawText(QRectF(kx + 10, ky + 4, kw - 20, 14),
                   Qt.AlignmentFlag.AlignLeft, _ay_etiket(a.ay))
        for k, (ad, deg, renk) in enumerate(satirlar):
            y = ky + 20 + k * 14
            p.setPen(QPen(QColor(renk)))
            p.drawText(QRectF(kx + 10, y, kw - 20, 14), Qt.AlignmentFlag.AlignLeft, ad)
            p.setPen(QPen(QColor(_DARK)))
            p.drawText(QRectF(kx + 10, y, kw - 20, 14), Qt.AlignmentFlag.AlignRight, deg)


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
    # Şişik rakamı sessizce basmak, boş bırakmaktan daha zararlı: kullanıcı mizan
    # stoğunu gerçek sanıp «bu artış imkânsız» diye rapora güvenini yitiriyor.
    stok_renk = NEG if tr.maliyet_eksik else _DARK
    _tsatir(t, [_c("Stok" + (" ⚠" if tr.maliyet_eksik else ""), renk=stok_renk),
                _c(tl(tr.stok), renk=stok_renk, sag=True)])
    _fit_height(t)
    kart = _card("BİLANÇO ÖZETİ", _ic(t))
    if tr.maliyet_eksik:
        _uyari_ekle(kart, MALIYET_EKSIK_UYARI)
    return kart


def _uyari_ekle(kart: QFrame, metin: str) -> None:
    """Kartın altına sarı şeritli uyarı ekler (kartın kendi düzenine)."""
    lay = kart.layout()
    if lay is None:
        return
    et = QLabel(metin)
    et.setWordWrap(True)
    et.setStyleSheet(
        "background: #fff8e1; border: 1px solid #f0d48a; border-radius: 6px;"
        "color: #7a5b00; font-size: 11px; padding: 7px 9px;")
    lay.addWidget(et)


def _trend_panel(tr: TrendRapor) -> QFrame:
    aylar = tr.aylik_gecmis or tr.aylik
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        f"<span style='color:{_C_SATIS};'>■</span> Satış &nbsp;&nbsp;"
        f"<span style='color:{_C_ALIS};'>■</span> Alış &nbsp;&nbsp;"
        f"<span style='color:{_C_NAKIT};'>▬</span> Net Nakit (kasaya giren − çıkan)"
        f"<span style='color:{FAINT};'> &nbsp;·&nbsp; iki çubuk arasındaki fark brüt kârdır "
        "&nbsp;·&nbsp; ay üstüne gelince rakamlar çıkar</span>"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TrendChart(aylar))
    baslik = "AYLIK TREND"
    if len(aylar) > len(tr.aylik):
        baslik += f"  ·  son {len(aylar)} ay"
    return _card(baslik, inner)


def build_trend_widget(tr: TrendRapor, firma: str = "",
                       kapanislar: list | None = None) -> QWidget:
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

    # Yıllar arası mukayese en altta — API anahtarı gerektirmez, yorum sekmesinden
    # buraya taşındı (aynı veri iki sekmede tekrarlanmasın).
    mukayese = mukayese_karti(kapanislar or [])
    if mukayese is not None:
        root.addWidget(mukayese)

    root.addStretch(1)
    return content
