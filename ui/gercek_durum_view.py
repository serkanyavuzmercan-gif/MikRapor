"""
Nakit & Kârlılık — yerel Qt görünümü.

İşletmenin fiili kârlılık ve nakit performansını gösterir: stok hareketinden fiili brüt marj,
banka hareketinden nakit akışı, 10x/12x/32x bakiyelerinden nakit/alacak/borç. "RESMİ vs FİİLİ"
paneli, resmi gelir tablosu ile fiili operasyonu yan yana koyup farkın mutabakatını yapar
(SMM zamanlaması, 623 vb.). Aylık trend grafiği ek bağımlılık olmadan QPainter ile çizilir.
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

from domain.gercek_durum import GercekDurum, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _kpi_card
from ui.styles import BAD as NEG, BORDER, OK as POZ, PANEL_BG


def _renk(v: float) -> str:
    return POZ if v >= 0 else NEG


def _card(baslik: str, inner: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("gdCard")
    card.setStyleSheet(
        f"QFrame#gdCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}"
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
    lbl = QLabel(text)
    w = "800" if bold else "400"
    lbl.setStyleSheet(
        f"color: {renk}; font-size: {boyut}px; font-weight: {w}; background: transparent;"
    )
    if sag:
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


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
    satir(0, f"Fiili Satış  ({baz})", tl(gd.gercek_satis), bold=True)
    g.addWidget(_satir_label("    • satış irsaliyesi", renk=FAINT, boyut=11), 1, 0)
    g.addWidget(_satir_label(tl(gd.satis_irsaliye), renk=FAINT, boyut=11, sag=True), 1, 1)
    g.addWidget(_satir_label("    • satış faturası", renk=FAINT, boyut=11), 2, 0)
    g.addWidget(_satir_label(tl(gd.satis_fatura), renk=FAINT, boyut=11, sag=True), 2, 1)
    satir(3, "Fiili Alış (−)", tl(-gd.gercek_alis))
    g.addWidget(_satir_label("    • alış faturası (toplam alış)", renk=FAINT, boyut=11), 4, 0)
    g.addWidget(_satir_label(tl(gd.alis_fatura), renk=FAINT, boyut=11, sag=True), 4, 1)
    r_extra = 5
    if gd.alis_irsaliye > 0.005 and gd.gercek_alis != gd.alis_irsaliye:
        g.addWidget(_satir_label(
            "    • alış irsaliyesi (bilgi — çift sayım olmasın diye toplama dahil değil)",
            renk=FAINT, boyut=11), 5, 0)
        g.addWidget(_satir_label(tl(gd.alis_irsaliye), renk=FAINT, boyut=11, sag=True), 5, 1)
        r_extra = 6
    if gd.siniflandirilmayan_giris > 0.005:
        g.addWidget(_satir_label("    • diğer giriş (evraktip?)", renk=FAINT, boyut=11), r_extra, 0)
        g.addWidget(_satir_label(tl(gd.siniflandirilmayan_giris), renk=FAINT, boyut=11, sag=True), r_extra, 1)
        r_brut = r_extra + 1
    else:
        r_brut = r_extra
    satir(r_brut, "Fiili Brüt Kâr", tl(gd.gercek_brut_kar), bold=True, renk=_renk(gd.gercek_brut_kar))
    satir(r_brut + 1, "Fiili Brüt Marj", yuzde(gd.gercek_brut_marj), bold=True,
          renk=_renk(gd.gercek_brut_marj))
    if gd.resmi_smm is not None and gd.smm_stok_farki is not None:
        not2 = _satir_label(
            f"Resmi SMM (GL 62xx) {tl(gd.resmi_smm)} − stok alış {tl(gd.gercek_alis)} "
            f"= {tl(gd.smm_stok_farki)} fark (623, stok değişimi, maliyet kapanışı).",
            renk=FAINT, boyut=11)
        not2.setWordWrap(True)
        g.addWidget(not2, r_brut + 2, 0, 1, 2)
    return _card("OPERASYONEL KÂRLILIK  (stok hareketinden)", inner)


def _karsilastirma_panel(gd: GercekDurum) -> QFrame:
    inner = QWidget()
    inner.setStyleSheet("background: transparent;")
    g = QGridLayout(inner)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    g.setColumnStretch(0, 1)

    for c, baslik in ((1, "Resmi"), (2, "Fiili"), (3, "Fark")):
        g.addWidget(_satir_label(baslik, renk=MUTED, boyut=11, bold=True, sag=True), 0, c)

    def kolon3(r: int, ad: str, resmi: str, gercek: str, fark: str, fark_renk: str) -> None:
        g.addWidget(_satir_label(ad, bold=True), r, 0)
        g.addWidget(_satir_label(resmi, sag=True), r, 1)
        g.addWidget(_satir_label(gercek, sag=True, bold=True), r, 2)
        g.addWidget(_satir_label(fark, sag=True, bold=True, renk=fark_renk), r, 3)

    if gd.resmi_brut_marj is None:
        g.addWidget(_satir_label("Resmi gelir tablosu yüklenemedi.", renk=FAINT), 1, 0, 1, 4)
        return _card("RESMİ vs FİİLİ", inner)

    mf = gd.marj_farki or 0.0
    kolon3(1, "Brüt Marj", yuzde(gd.resmi_brut_marj), yuzde(gd.gercek_brut_marj),
           ("+" if mf >= 0 else "") + yuzde(mf), _renk(mf))
    if gd.resmi_brut_kar is not None:
        bk_fark = gd.gercek_brut_kar - gd.resmi_brut_kar
        kolon3(2, "Brüt Kâr", tl(gd.resmi_brut_kar), tl(gd.gercek_brut_kar),
               ("+" if bk_fark >= 0 else "") + tl(bk_fark), _renk(bk_fark))
    if gd.resmi_smm is not None:
        sf = gd.smm_stok_farki or 0.0
        kolon3(3, "Maliyet (SMM / Stok Alış)",
               tl(gd.resmi_smm), tl(gd.gercek_alis),
               ("+" if sf >= 0 else "") + tl(sf), _renk(-sf))
    if gd.gizlenen_brut is not None:
        g.addWidget(_satir_label("Fiili − resmi brüt farkı (yaklaşık)", bold=True), 4, 0)
        g.addWidget(_satir_label(("+" if gd.gizlenen_brut >= 0 else "") + tl(gd.gizlenen_brut),
                                 sag=True, bold=True, renk=_renk(gd.gizlenen_brut)), 4, 1, 1, 3)

    not_lbl = _satir_label(
        "Fiili marj = depodan çıkan − giren mal. Resmi SMM ek olarak 623 (navlun/gümrük vb.) ve "
        "dönem stok değişimini içerir; iki rakam bu yüzden farklı çıkar. Fark muhasebe "
        "zamanlamasıdır, bir tutarsızlık değildir.",
        renk=FAINT, boyut=11)
    not_lbl.setWordWrap(True)
    g.addWidget(not_lbl, 5, 0, 1, 4)
    return _card("RESMİ vs FİİLİ  (mutabakat)", inner)


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
    satir(4, "Nakit Mevcudu (banka+kasa)", tl(gd.nakit_mevcut), bold=True,
          renk=_renk(gd.nakit_mevcut))
    if gd.nakit_banka > 0.005 or gd.nakit_kasa > 0.005:
        g.addWidget(_satir_label("    • banka", renk=FAINT, boyut=11), 5, 0)
        g.addWidget(_satir_label(tl(gd.nakit_banka), renk=FAINT, boyut=11, sag=True), 5, 1)
        g.addWidget(_satir_label("    • kasa", renk=FAINT, boyut=11), 6, 0)
        g.addWidget(_satir_label(tl(gd.nakit_kasa), renk=FAINT, boyut=11, sag=True), 6, 1)
        r_kaynak = 7
    else:
        r_kaynak = 5
    kaynak = {
        "cari": "Alacak/borç: cari · Nakit: cari",
        "cari+gl": "Alacak/borç: cari · Nakit: GL mizan",
        "gl": "Alacak/borç: cari · Nakit: GL mizan",
        "mizan": "Alacak/borç ve nakit: GL mizan",
        "bakiye_ozet": "GL özet bakiyelerinden",
    }.get(gd.bakiye_kaynagi, "")
    if kaynak:
        not_k = _satir_label(kaynak, renk=FAINT, boyut=10)
        g.addWidget(not_k, r_kaynak, 0, 1, 2)
        r_alacak = r_kaynak + 1
    else:
        r_alacak = r_kaynak
    satir(r_alacak, "Alacaklar (müşteri)", tl(gd.alacak))
    if gd.musteri_avans > 0.005 and gd.musteri_avans_goster:
        satir(r_alacak + 1, "Müşteri avansı (−)", tl(-gd.musteri_avans), renk=NEG)
        r_borc = r_alacak + 2
    else:
        r_borc = r_alacak + 1
    satir(r_borc, "Borçlar (satıcı)", tl(gd.borc), renk=NEG if gd.borc else "#374151")
    if gd.satici_avans > 0.005:
        satir(r_borc + 1, "Satıcı avansı", tl(gd.satici_avans), renk=POZ)
        r_nis = r_borc + 2
    else:
        r_nis = r_borc + 1
    satir(r_nis, "Net İşletme Sermayesi", tl(gd.net_isletme_sermayesi), bold=True,
          renk=_renk(gd.net_isletme_sermayesi))
    if gd.gl_alacak is not None and gd.bakiye_kaynagi in ("cari", "cari+gl", "gl"):
        fark = abs((gd.gl_alacak or 0) - gd.alacak) + abs((gd.gl_borc or 0) - gd.borc)
        if fark > 1000:
            not_gl = _satir_label(
                f"GL mizan farkı: alacak {tl(gd.gl_alacak)} · borç {tl(gd.gl_borc or 0)} "
                f"· nakit {tl(gd.gl_nakit_mevcut or 0)} — cari ile GL uyumsuz olabilir.",
                renk="#b45309", boyut=10)
            not_gl.setWordWrap(True)
            g.addWidget(not_gl, r_nis + 1, 0, 1, 2)
    return _card("NAKİT & İŞLETME SERMAYESİ  (cari bakiye)", inner)


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
        renkler = (QColor(ACCENT), QColor(POZ), QColor("#d97706"))

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
        f"<span style='color:{ACCENT};'>■</span> Satış &nbsp;&nbsp;"
        f"<span style='color:{POZ};'>■</span> Brüt Kâr &nbsp;&nbsp;"
        "<span style='color:#d97706;'>■</span> Net Nakit"
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
    profil = (
        f"<br><span style='font-size:10px;'>Profil: {gd.ayar_ozet}</span>" if gd.ayar_ozet else ""
    )
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>NAKİT &amp; KÂRLILIK &nbsp;·&nbsp; "
        f"{gd.bas} → {gd.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Doğrudan Mikro'dan — faturalar "
        f"muhasebeleştirilmeden, deponuzdan geçen mal ve bankadan geçen para üzerinden "
        f"işletmenin fiili kârlılığını ve nakdini hesaplar.{profil}</span>"
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

    # Hero: fiili brüt marj önde (Teal A)
    hero = QFrame()
    hero.setObjectName("gdHero")
    hero.setStyleSheet(
        f"QFrame#gdHero {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 14px; }}"
    )
    hl = QHBoxLayout(hero)
    hl.setContentsMargins(20, 16, 20, 16)
    hl.setSpacing(24)
    hero_left = QVBoxLayout()
    hero_left.setSpacing(2)
    hb = QLabel("FİİLİ BRÜT MARJ")
    hb.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
    hv = QLabel(yuzde(gd.gercek_brut_marj))
    hv.setStyleSheet(
        f"color: {_renk(gd.gercek_brut_marj)}; font-size: 32px; font-weight: 800;"
    )
    hs = QLabel(f"Fiili brüt kâr {tl(gd.gercek_brut_kar)}  ·  satış {tl(gd.gercek_satis)}")
    hs.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
    hero_left.addWidget(hb)
    hero_left.addWidget(hv)
    hero_left.addWidget(hs)
    hl.addLayout(hero_left, 2)
    for baslik, deger, vr in (
        ("NET NAKİT AKIŞI", tl(gd.nakit_net), _renk(gd.nakit_net)),
        ("NET İŞLETME SERMAYESİ", tl(gd.net_isletme_sermayesi), _renk(gd.net_isletme_sermayesi)),
    ):
        col = QVBoxLayout()
        col.setSpacing(2)
        lb = QLabel(baslik)
        lb.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600;")
        col.addWidget(lb)
        dv = QLabel(deger)
        dv.setStyleSheet(f"color: {vr}; font-size: 16px; font-weight: 800;")
        col.addWidget(dv)
        hl.addLayout(col, 1)
    root.addWidget(hero)

    row1 = QHBoxLayout()
    row1.setSpacing(20)
    row1.addWidget(_operasyonel_panel(gd), 1)
    row1.addWidget(_karsilastirma_panel(gd), 1)
    root.addLayout(row1)

    root.addWidget(_trend_panel(gd))
    root.addWidget(_nakit_panel(gd))
    root.addStretch(1)
    return content
