"""
Nakit & Kârlılık — yerel Qt görünümü.

İşletmenin fiili kârlılık ve nakit performansını gösterir: stok hareketinden fiili brüt marj,
banka hareketinden nakit akışı, 10x/12x/32x bakiyelerinden nakit/alacak/borç. "RESMİ vs FİİLİ"
paneli, resmi gelir tablosu ile fiili operasyonu yan yana koyup farkın mutabakatını yapar
(SMM zamanlaması, 623 vb.). Aylık trend grafiği ek bağımlılık olmadan QPainter ile çizilir.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.gercek_durum import GercekDurum, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_view import _TREE_QSS, ACCENT, FAINT, MUTED, PAGE_BG, _fit_height
from ui.styles import BAD as NEG
from ui.styles import BORDER, PANEL_BG
from ui.styles import OK as POZ

# Tablo yazı hiyerarşisi: ana satır koyu, alt kalem okunur gri (FAINT değil).
_DARK = "#1f2937"
_MID = "#475569"


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


def _agac(kolon: int, sabit: list[tuple[int, int]]) -> QTreeWidget:
    """Hover + zebra'lı, seçimsiz mini tablo. col0 esner; `sabit` kolonlar sabit genişlik."""
    t = QTreeWidget()
    t.setColumnCount(kolon)
    t.setHeaderHidden(True)
    t.setRootIsDecorated(False)
    t.setIndentation(0)
    t.setUniformRowHeights(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setAlternatingRowColors(True)
    t.setMouseTracking(True)
    t.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    t.viewport().setMouseTracking(True)
    t.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    t.setStyleSheet(_TREE_QSS)
    hdr = t.header()
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for c, w in sabit:
        hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
        t.setColumnWidth(c, w)
    return t


def _c(text: str, *, renk: str = _DARK, kalin: bool = False, sag: bool = False) -> tuple:
    """Bir hücre tarifi (metin, renk, kalınlık, sağa-yaslı)."""
    return (text, renk, kalin, sag)


def _tsatir(t: QTreeWidget, hucreler: list[tuple]) -> QTreeWidgetItem:
    it = QTreeWidgetItem([h[0] for h in hucreler])
    it.setSizeHint(0, QSize(0, 30))
    for c, (_text, renk, kalin, sag) in enumerate(hucreler):
        f = it.font(c)
        f.setBold(kalin)
        it.setFont(c, f)
        it.setForeground(c, QBrush(QColor(renk)))
        if sag:
            it.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    t.addTopLevelItem(it)
    return it


def _ic(tree: QTreeWidget, notlar: list[tuple[str, str]] = ()) -> QWidget:
    """Ağaç + (varsa) altına açıklama notları."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(8)
    v.addWidget(tree)
    for metin, renk in notlar:
        lbl = QLabel(metin)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {renk}; font-size: 11px; background: transparent;")
        v.addWidget(lbl)
    return w


def _operasyonel_panel(gd: GercekDurum) -> QFrame:
    t = _agac(2, [(1, 150)])
    baz = "İrsaliye + Fatura" if gd.satis_bazi == "sevk" else "Yalnız Fatura"
    _tsatir(t, [_c(f"Fiili Satış  ({baz})", kalin=True),
                _c(tl(gd.gercek_satis), kalin=True, sag=True)])
    _tsatir(t, [_c("      satış irsaliyesi", renk=_MID),
                _c(tl(gd.satis_irsaliye), renk=_MID, sag=True)])
    _tsatir(t, [_c("      satış faturası", renk=_MID),
                _c(tl(gd.satis_fatura), renk=_MID, sag=True)])
    _tsatir(t, [_c("Fiili Alış (−)", kalin=True),
                _c(tl(-gd.gercek_alis), kalin=True, sag=True)])
    _tsatir(t, [_c("      alış faturası (toplam alış)", renk=_MID),
                _c(tl(gd.alis_fatura), renk=_MID, sag=True)])
    if gd.alis_irsaliye > 0.005 and gd.gercek_alis != gd.alis_irsaliye:
        _tsatir(t, [_c("      alış irsaliyesi (dahil değil)", renk=_MID),
                    _c(tl(gd.alis_irsaliye), renk=_MID, sag=True)])
    if gd.siniflandirilmayan_giris > 0.005:
        _tsatir(t, [_c("      diğer giriş (tanınmayan)", renk=_MID),
                    _c(tl(gd.siniflandirilmayan_giris), renk=_MID, sag=True)])
    _tsatir(t, [_c("Fiili Al-Sat Farkı", kalin=True),
                _c(tl(gd.gercek_brut_kar), renk=_renk(gd.gercek_brut_kar), kalin=True, sag=True)])
    _tsatir(t, [_c("Fiili Al-Sat Marjı", kalin=True),
                _c(yuzde(gd.gercek_brut_marj), renk=_renk(gd.gercek_brut_marj), kalin=True, sag=True)])
    _fit_height(t)

    notlar: list[tuple[str, str]] = []
    if gd.resmi_smm is not None and gd.smm_stok_farki is not None:
        notlar.append((
            f"Resmi SMM (GL 62xx) {tl(gd.resmi_smm)} − stok alış {tl(gd.gercek_alis)} "
            f"= {tl(gd.smm_stok_farki)} fark (623, stok değişimi, maliyet kapanışı).", MUTED))
    return _card("OPERASYONEL KÂRLILIK  (stok hareketinden)", _ic(t, notlar))


def _karsilastirma_panel(gd: GercekDurum) -> QFrame:
    t = _agac(4, [(1, 118), (2, 132), (3, 128)])
    _tsatir(t, [_c(""), _c("Resmi", renk=MUTED, kalin=True, sag=True),
                _c("Fiili", renk=MUTED, kalin=True, sag=True),
                _c("Fark", renk=MUTED, kalin=True, sag=True)])

    if gd.resmi_brut_marj is None:
        _tsatir(t, [_c("Resmi gelir tablosu yüklenemedi.", renk=_MID), _c(""), _c(""), _c("")])
        _fit_height(t)
        return _card("RESMİ vs FİİLİ", _ic(t))

    mf = gd.marj_farki or 0.0
    _tsatir(t, [_c("Brüt Marj", kalin=True), _c(yuzde(gd.resmi_brut_marj), sag=True),
                _c(yuzde(gd.gercek_brut_marj), kalin=True, sag=True),
                _c(("+" if mf >= 0 else "") + yuzde(mf), renk=_renk(mf), kalin=True, sag=True)])
    if gd.resmi_brut_kar is not None:
        bk = gd.gercek_brut_kar - gd.resmi_brut_kar
        _tsatir(t, [_c("Brüt Kâr", kalin=True), _c(tl(gd.resmi_brut_kar), sag=True),
                    _c(tl(gd.gercek_brut_kar), kalin=True, sag=True),
                    _c(("+" if bk >= 0 else "") + tl(bk), renk=_renk(bk), kalin=True, sag=True)])
    if gd.resmi_smm is not None:
        sf = gd.smm_stok_farki or 0.0
        _tsatir(t, [_c("Maliyet (SMM / Stok Alış)", kalin=True), _c(tl(gd.resmi_smm), sag=True),
                    _c(tl(gd.gercek_alis), kalin=True, sag=True),
                    _c(("+" if sf >= 0 else "") + tl(sf), renk=_renk(-sf), kalin=True, sag=True)])
    if gd.gizlenen_brut is not None:
        _tsatir(t, [_c("Fiili − resmi fark (yaklaşık)", kalin=True), _c(""), _c(""),
                    _c(("+" if gd.gizlenen_brut >= 0 else "") + tl(gd.gizlenen_brut),
                       renk=_renk(gd.gizlenen_brut), kalin=True, sag=True)])
    _fit_height(t)

    notlar = [(
        "Fiili marj = depodan çıkan − giren mal. Resmi SMM ek olarak 623 (navlun/gümrük vb.) ve "
        "dönem stok değişimini içerir; iki rakam bu yüzden farklı çıkar. Fark muhasebe "
        "zamanlamasıdır, bir tutarsızlık değildir.", MUTED)]
    return _card("RESMİ vs FİİLİ  (mutabakat)", _ic(t, notlar))


def _isletme_sermayesi_panel(gd: GercekDurum) -> QFrame:
    """İşini kendi kaynağıyla döndürebiliyor mu? — bu taba ÖZGÜ sentez.

    Nakit akışı Nakit Akış tab'ının, alacak/borç dökümü Tahsilat tab'ının işi;
    burada yalnızca 'işletme sermayesi' denklemini (nakit + net alacak − net borç)
    tek rakama indirgeriz — başka hiçbir tab bu sentezi yapmıyor.
    """
    net_alacak = gd.alacak - gd.musteri_avans
    net_borc = gd.borc - gd.satici_avans

    t = _agac(2, [(1, 160)])
    _tsatir(t, [_c("Nakit (banka + kasa)"), _c(tl(gd.nakit_mevcut), sag=True)])
    _tsatir(t, [_c("Tahsil edilecek (net alacak)"), _c(tl(net_alacak), renk=POZ, sag=True)])
    _tsatir(t, [_c("Ödenecek (net borç) (−)"), _c(tl(-net_borc), renk=NEG, sag=True)])
    _tsatir(t, [_c("Net İşletme Sermayesi", kalin=True),
                _c(tl(gd.net_isletme_sermayesi), renk=_renk(gd.net_isletme_sermayesi),
                   kalin=True, sag=True)])
    _fit_height(t)

    if gd.net_isletme_sermayesi >= 0:
        yorum = ("İşletme sermayesi = nakit + tahsil edeceklerin − ödeyeceklerin. "
                 "<b>Pozitif</b> — günlük işini büyük ölçüde kendi kaynağınla döndürebiliyorsun.")
    else:
        yorum = ("İşletme sermayesi = nakit + tahsil edeceklerin − ödeyeceklerin. "
                 "<b>Eksi</b> — kısa vadeli borçların nakit+alacağını aşıyor; işi döndürmek için "
                 "dış kaynak (kredi / öz sermaye) gerekir.")
    notlar: list[tuple[str, str]] = [(yorum, MUTED)]
    if gd.gl_alacak is not None and gd.bakiye_kaynagi in ("cari", "cari+gl", "gl"):
        fark = abs((gd.gl_alacak or 0) - gd.alacak) + abs((gd.gl_borc or 0) - gd.borc)
        if fark > 1000:
            notlar.append((
                f"GL mizan farkı: alacak {tl(gd.gl_alacak)} · borç {tl(gd.gl_borc or 0)} "
                f"· nakit {tl(gd.gl_nakit_mevcut or 0)} — cari ile GL uyumsuz olabilir.", "#b45309"))
    return _card("İŞLETME SERMAYESİ  (günlük işi çevirecek net kaynak)", _ic(t, notlar))


def _cizgi() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #e2e6ec; background: #e2e6ec;")
    f.setFixedHeight(1)
    return f


def build_gercek_durum_widget(gd: GercekDurum, firma: str = "") -> QWidget:
    """Bir GercekDurum'dan QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("gdContent")
    content.setStyleSheet("QWidget#gdContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
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
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, gd.bit, kaynak="canli"))

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

    # Bulgular kartı — ham sayıları aksiyona dönük yoruma çevirir (boşsa gizli)
    from domain.bulgular import gercek_durum_bulgulari
    from ui.bilesenler import bulgular_karti
    kart = bulgular_karti(gercek_durum_bulgulari(gd))
    if kart is not None:
        root.addWidget(kart)

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
    hb = QLabel("FİİLİ AL-SAT MARJI")
    hb.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
    hv = QLabel(yuzde(gd.gercek_brut_marj))
    hv.setStyleSheet(
        f"color: {_renk(gd.gercek_brut_marj)}; font-size: 32px; font-weight: 800;"
    )
    hs = QLabel(
        f"satış {tl(gd.gercek_satis)} − dönem alışı {tl(gd.gercek_alis)}  ·  "
        f"stok hareketinden (SMM'e dayalı brüt marj değil)"
    )
    hs.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
    hero_left.addWidget(hb)
    hero_left.addWidget(hv)
    hero_left.addWidget(hs)
    hl.addLayout(hero_left, 2)
    # Hero metrikleri bu taba ÖZGÜ: fiili brüt kâr (TL) + işletme sermayesi.
    # Net nakit akışı Nakit Akış tab'ının manşeti olduğu için burada tekrarlanmaz.
    for baslik, deger, vr in (
        ("FİİLİ BRÜT KÂR", tl(gd.gercek_brut_kar), _renk(gd.gercek_brut_kar)),
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
    # Üç tablo yan yana: İşletme Sermayesi (bu taba özgü, öne çıkan) + Operasyonel + Mutabakat.
    # Yan yana dizmek hem yatay boşluğu değerlendirir hem tek sütunlu tablodaki dev boşluğu keser.
    # Mutabakat 4 sütunlu olduğu için biraz daha geniş pay (3:3:4).
    row1 = QHBoxLayout()
    row1.setSpacing(16)
    row1.addWidget(_isletme_sermayesi_panel(gd), 3)
    row1.addWidget(_operasyonel_panel(gd), 3)
    row1.addWidget(_karsilastirma_panel(gd), 4)
    root.addLayout(row1)
    root.addStretch(1)
    return content
