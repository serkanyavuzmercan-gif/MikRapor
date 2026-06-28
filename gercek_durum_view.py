"""
Gerçek Durum — yerel Qt görünümü.

Resmi tabloların aksine operasyonel gerçeği gösterir: stok hareketinden gerçek brüt marj,
banka hareketinden nakit akışı, 10x/12x/32x bakiyelerinden nakit/alacak/borç. Vurucu kısım
"RESMİ vs GERÇEK" paneli: mali müşavirin marjı sektör ortalamasına çekerken gizlediği farkı
sayısal gösterir. Aylık trend grafiği ek bağımlılık olmadan QPainter ile çizilir.
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

from bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from gercek_durum import GercekDurum, yuzde
from mizan_bilanco import tl

POZ = "#15803d"   # yeşil (iyi/pozitif)
NEG = "#b91c1c"   # kırmızı (kötü/negatif)
PANEL_BG = "#f7f9fc"


def _renk(v: float) -> str:
    return POZ if v >= 0 else NEG


def _card(baslik: str, inner: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("gdCard")
    card.setStyleSheet(
        "QFrame#gdCard { background: %s; border: 1px solid #e3e8ef; border-radius: 12px; }"
        % PANEL_BG
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    lbl = QLabel(baslik)
    lbl.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: 800; background: transparent;")
    lay.addWidget(lbl)
    lay.addWidget(inner)
    lay.addStretch(1)
    return card


def _satir_label(text: str, *, renk: str = "#374151", bold: bool = False,
                 boyut: int = 12, sag: bool = False) -> QLabel:
    l = QLabel(text)
    w = "800" if bold else "400"
    l.setStyleSheet(
        f"color: {renk}; font-size: {boyut}px; font-weight: {w}; background: transparent;"
    )
    if sag:
        l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return l


def _operasyonel_panel(gd: GercekDurum) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(7)
    g.setColumnStretch(0, 1)

    def satir(r: int, ad: str, deger: str, *, bold: bool = False, renk: str = "#374151") -> None:
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, renk=renk, sag=True), r, 1)

    baz = "İrsaliye + Fatura" if gd.satis_bazi == "sevk" else "Yalnız Fatura"
    satir(0, f"Gerçek Satış  ({baz})", tl(gd.gercek_satis), bold=True)
    g.addWidget(_satir_label(f"    • satış irsaliyesi", renk=FAINT, boyut=11), 1, 0)
    g.addWidget(_satir_label(tl(gd.satis_irsaliye), renk=FAINT, boyut=11, sag=True), 1, 1)
    g.addWidget(_satir_label(f"    • satış faturası", renk=FAINT, boyut=11), 2, 0)
    g.addWidget(_satir_label(tl(gd.satis_fatura), renk=FAINT, boyut=11, sag=True), 2, 1)
    satir(3, "Gerçek Alış (−)", tl(-gd.gercek_alis))
    satir(4, "Gerçek Brüt Kâr", tl(gd.gercek_brut_kar), bold=True, renk=_renk(gd.gercek_brut_kar))
    satir(5, "Gerçek Brüt Marj", yuzde(gd.gercek_brut_marj), bold=True,
          renk=_renk(gd.gercek_brut_marj))
    return _card("OPERASYONEL GERÇEK  (stok hareketinden)", inner)


def _karsilastirma_panel(gd: GercekDurum) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    for c, baslik in ((1, "Resmi"), (2, "Gerçek"), (3, "Fark")):
        g.addWidget(_satir_label(baslik, renk=MUTED, boyut=11, bold=True, sag=True), 0, c)

    def kolon3(r: int, ad: str, resmi: str, gercek: str, fark: str, fark_renk: str) -> None:
        g.addWidget(_satir_label(ad, bold=True), r, 0)
        g.addWidget(_satir_label(resmi, sag=True), r, 1)
        g.addWidget(_satir_label(gercek, sag=True, bold=True), r, 2)
        g.addWidget(_satir_label(fark, sag=True, bold=True, renk=fark_renk), r, 3)

    if gd.resmi_brut_marj is None:
        g.addWidget(_satir_label("Resmi gelir tablosu yüklenemedi.", renk=FAINT), 1, 0, 1, 4)
        return _card("RESMİ vs GERÇEK", inner)

    mf = gd.marj_farki or 0.0
    kolon3(1, "Brüt Marj", yuzde(gd.resmi_brut_marj), yuzde(gd.gercek_brut_marj),
           ("+" if mf >= 0 else "") + yuzde(mf), _renk(mf))
    if gd.resmi_brut_kar is not None:
        bk_fark = gd.gercek_brut_kar - gd.resmi_brut_kar
        kolon3(2, "Brüt Kâr", tl(gd.resmi_brut_kar), tl(gd.gercek_brut_kar),
               ("+" if bk_fark >= 0 else "") + tl(bk_fark), _renk(bk_fark))
    if gd.gizlenen_brut is not None:
        g.addWidget(_satir_label("Gizlenen brüt (yaklaşık)", bold=True), 3, 0)
        g.addWidget(_satir_label(("+" if gd.gizlenen_brut >= 0 else "") + tl(gd.gizlenen_brut),
                                 sag=True, bold=True, renk=_renk(gd.gizlenen_brut)), 3, 1, 1, 3)

    not_lbl = _satir_label(
        "Operasyonel marj (Satış − Alış) stok değişimini içermez; resmi brüt karla farkı "
        "genelde stok hareketi + 602/623 'Diğer' kalemlerinden gelir.",
        renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, 4, 0, 1, 4)
    return _card("RESMİ vs GERÇEK  (gizlenen marj)", inner)


def _nakit_panel(gd: GercekDurum) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(7)
    g.setColumnStretch(0, 1)

    def satir(r: int, ad: str, deger: str, *, bold: bool = False, renk: str = "#374151") -> None:
        g.addWidget(_satir_label(ad, bold=bold), r, 0)
        g.addWidget(_satir_label(deger, bold=bold, renk=renk, sag=True), r, 1)

    satir(0, "Para Giren (tahsilat)", tl(gd.nakit_giren), renk=POZ)
    satir(1, "Para Çıkan (tediye) (−)", tl(-gd.nakit_cikan), renk=NEG)
    satir(2, "Net Nakit Akışı", tl(gd.nakit_net), bold=True, renk=_renk(gd.nakit_net))
    g.addWidget(_cizgi(), 3, 0, 1, 2)
    satir(4, "Nakit Mevcudu (kasa+banka)", tl(gd.nakit_mevcut), bold=True,
          renk=_renk(gd.nakit_mevcut))
    satir(5, "Alacaklar (müşteri 12x)", tl(gd.alacak))
    if gd.musteri_avans > 0.005:
        satir(6, "Müşteri avansı (12x alacak bak.) (−)", tl(-gd.musteri_avans), renk=NEG)
        r_borc = 7
    else:
        r_borc = 6
    satir(r_borc, "Borçlar (satıcı 32x)", tl(gd.borc), renk=NEG if gd.borc else "#374151")
    if gd.satici_avans > 0.005:
        satir(r_borc + 1, "Satıcı avansı (32x borç bak.)", tl(gd.satici_avans), renk=POZ)
        r_nis = r_borc + 2
    else:
        r_nis = r_borc + 1
    satir(r_nis, "Net İşletme Sermayesi", tl(gd.net_isletme_sermayesi), bold=True,
          renk=_renk(gd.net_isletme_sermayesi))
    return _card("NAKİT GERÇEĞİ & İŞLETME SERMAYESİ  (banka + bakiye)", inner)


def _cizgi() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #e2e6ec; background: #e2e6ec;")
    f.setFixedHeight(1)
    return f


class _TrendChart(QWidget):
    """Aylık Satış, Brüt Kâr ve Net Nakit'i ek bağımlılık olmadan çizen mini grafik."""

    def __init__(self, gd: GercekDurum, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._aylar = gd.trend
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _ev) -> None:  # noqa: N802 (Qt override)
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
        # Net nakit negatif olabildiği için ölçek [min, max] aralığına ve 0 çizgisine göre
        min_v = min((min(s, b, n) for s, b, n in seriler), default=0.0)
        max_v = max((max(s, b, n) for s, b, n in seriler), default=0.0)
        min_v = min(min_v, 0.0)
        max_v = max(max_v, 0.0)
        span = (max_v - min_v) or 1.0

        n = len(self._aylar)
        grup_w = cw / n
        bar_w = min(18.0, grup_w / 4.2)
        renkler = (QColor("#2f6fed"), QColor("#15803d"), QColor("#f59e0b"))

        def y_of(v: float) -> float:
            return ust + ch * ((max_v - v) / span)

        # sıfır çizgisi
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
            ay_kisa = a.ay[2:] if len(a.ay) >= 7 else a.ay  # 'YY-MM'
            p.drawText(QRectF(sol + grup_w * i, h - alt + 4, grup_w, alt - 6),
                       Qt.AlignmentFlag.AlignCenter, ay_kisa)
        p.end()


def _trend_panel(gd: GercekDurum) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)
    lej = QLabel(
        "<span style='color:#2f6fed;'>■</span> Satış &nbsp;&nbsp;"
        "<span style='color:#15803d;'>■</span> Brüt Kâr &nbsp;&nbsp;"
        "<span style='color:#f59e0b;'>■</span> Net Nakit"
    )
    lej.setStyleSheet("font-size: 11px; background: transparent;")
    lej.setTextFormat(Qt.TextFormat.RichText)
    v.addWidget(lej)
    v.addWidget(_TrendChart(gd))
    return _card("AYLIK TREND", inner)


def build_gercek_durum_widget(gd: GercekDurum, firma: str = "") -> QWidget:
    """Bir GercekDurum'dan QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("gdContent")
    content.setStyleSheet("QWidget#gdContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(24, 18, 24, 24)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>GERÇEK DURUM &nbsp;·&nbsp; "
        f"{gd.bas} → {gd.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Doğrudan Mikro'dan — fiili stok ve banka "
        f"hareketine dayanır; resmi GL'nin oynanabilir kalemlerinden bağımsızdır.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    if gd.stok_kirilim_sayisi == 0:
        uyari = QLabel(
            "⚠ <b>Bu dönemde stok hareketi bulunamadı.</b> Mikro'da veri olan yılı/dönemi seçin "
            "(ör. 2025 tam yıl). Mikro Ayarları'ndaki <b>çalışma yılı</b> ile dönem tarihleri "
            "aynı olmalı."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdf3e0; border: 1px solid #f0d090; border-radius: 8px; "
            "color: #8a5a00; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)
    elif gd.siniflandirma_fallback:
        uyari = QLabel(
            "⚠ <b>Evrak tipi tanınmayan stok hareketleri var</b> — satış/alış toplamı tüm "
            "çıkış/giriş hareketlerinden hesaplandı (bilinen irsaliye/fatura kodları dışı kalanlar)."
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
    kpi.addWidget(_kpi_card("GERÇEK SATIŞ", tl(gd.gercek_satis), "#eef4ff", "#1d4ed8"))
    bk_bg, bk_vr = ("#e8f6ee", POZ) if gd.gercek_brut_kar >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card(f"GERÇEK BRÜT MARJ  ·  {yuzde(gd.gercek_brut_marj)}",
                            tl(gd.gercek_brut_kar), bk_bg, bk_vr))
    nk_bg, nk_vr = ("#e8f6ee", POZ) if gd.nakit_net >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("NET NAKİT AKIŞI", tl(gd.nakit_net), nk_bg, nk_vr))
    is_bg, is_vr = ("#e8f6ee", POZ) if gd.net_isletme_sermayesi >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("NET İŞLETME SERMAYESİ", tl(gd.net_isletme_sermayesi), is_bg, is_vr))
    root.addLayout(kpi)

    row1 = QHBoxLayout()
    row1.setSpacing(20)
    row1.addWidget(_operasyonel_panel(gd), 1)
    row1.addWidget(_karsilastirma_panel(gd), 1)
    root.addLayout(row1)

    row2 = QHBoxLayout()
    row2.setSpacing(20)
    row2.addWidget(_nakit_panel(gd), 1)
    row2.addWidget(_trend_panel(gd), 1)
    root.addLayout(row2)
    root.addStretch(1)
    return content
