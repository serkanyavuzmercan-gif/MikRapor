"""
Bilanço — yerel Qt görünümü (QTreeWidget panelleri + KPI kartları).

Neden HTML değil: bilanço gövdesi önceden QTextBrowser içinde HTML idi, ama Qt'nin
zengin-metin motoru CSS `:hover` desteklemez — satır üstüne gelince vurgulama yapılamaz.
Bu yüzden gövde yerel widget'larla çizilir: AKTİF | PASİF iki `QTreeWidget` paneli.
Satır üstüne gelince (`::item:hover`) satır açık maviyle vurgulanır (kullanıcı isteği).
Veri modeli (`Bilanco`) ve PDF çıktısı aynı kalır; yalnızca ekran görünümü yerelleşir.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
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

from domain.mizan_bilanco import AKTIF_BOLUM, PASIF_BOLUM, Bilanco, tl

# Renkler — açık tema (styles.py ile uyumlu)
NAVY = "#1f3a5f"
ACCENT = "#2f6fed"
INK = "#1f2937"
SUBINK = "#334155"
MUTED = "#6b7280"
FAINT = "#94a3b8"
PANEL_BG = "#f7f9fc"
PAGE_BG = "#f4f6f9"

_ALT_TOPLAM_ETIKET = {
    "1": "Dönen Varlıklar Toplamı",
    "2": "Duran Varlıklar Toplamı",
    "3": "Kısa Vadeli Yab. Kaynaklar Toplamı",
    "4": "Uzun Vadeli Yab. Kaynaklar Toplamı",
    "5": "Özkaynaklar Toplamı",
}

# Satır üstüne gelince vurgu — yerel widget olduğu için gerçek :hover çalışır.
_TREE_QSS = """
QTreeWidget {
    background: #ffffff;
    alternate-background-color: #f5f8fc;
    border: 1px solid #e3e8ef;
    border-radius: 10px;
    outline: 0;
    font-size: 12px;
}
QTreeWidget::item {
    padding: 6px 4px;
    color: #374151;
    border-bottom: 1px solid #e6eaf1;
}
QTreeWidget::item:hover {
    background: #d6e4fb;
    color: #0f172a;
}
"""


def _tree() -> QTreeWidget:
    t = QTreeWidget()
    t.setColumnCount(2)
    t.setHeaderHidden(True)
    t.setRootIsDecorated(False)
    t.setIndentation(0)
    t.setUniformRowHeights(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setAlternatingRowColors(True)  # zebra — satırları gözle ayırmayı kolaylaştırır
    # Satır :hover vurgusunun çalışması için viewport'ta mouse-tracking + WA_Hover şart.
    t.setMouseTracking(True)
    t.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    t.viewport().setMouseTracking(True)
    t.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    t.setStyleSheet(_TREE_QSS)
    hdr = t.header()
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    t.setColumnWidth(1, 138)
    return t


def _buyut(f: QFont, artis: float = 0.5) -> None:
    """Punto/piksel — hangisi tanımlıysa onu büyüt. Stylesheet px font'ta pointSizeF()=-1
    döner; doğrudan +0.5 yapmak 'Point size <= 0' uyarısı verir, o yüzden güvenli büyütme."""
    if f.pointSizeF() > 0:
        f.setPointSizeF(f.pointSizeF() + artis)
    elif f.pixelSize() > 0:
        f.setPixelSize(f.pixelSize() + 1)


def _section(t: QTreeWidget, baslik: str) -> None:
    it = QTreeWidgetItem([baslik, ""])
    f = it.font(0)
    f.setBold(True)
    _buyut(f)
    it.setFont(0, f)
    it.setForeground(0, QBrush(QColor(NAVY)))
    it.setFlags(Qt.ItemFlag.ItemIsEnabled)
    t.addTopLevelItem(it)
    it.setFirstColumnSpanned(True)  # eklendikten SONRA span çalışır


def _row(t: QTreeWidget, ad: str, tutar: float, *, bold: bool = False,
         renk: str | None = None, big: bool = False) -> None:
    it = QTreeWidgetItem([ad, tl(tutar)])
    it.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if bold or big:
        for c in (0, 1):
            f = it.font(c)
            f.setBold(True)
            if big:
                _buyut(f)
            it.setFont(c, f)
    if renk:
        br = QBrush(QColor(renk))
        it.setForeground(0, br)
        it.setForeground(1, br)
    t.addTopLevelItem(it)


def _fit_height(t: QTreeWidget) -> None:
    """Kendi scroll'unu kapat; dış scroll yönetsin diye yüksekliği içeriğe sabitle."""
    total = 2 * t.frameWidth()
    for i in range(t.topLevelItemCount()):
        h = t.sizeHintForRow(i)
        total += h if h > 0 else 26
    t.setFixedHeight(total + 4)


def _doldur(t: QTreeWidget, b: Bilanco, taraf: str) -> None:
    if taraf == "aktif":
        satirlar, bolumler = b.aktif, AKTIF_BOLUM
        toplam_etiket, toplam = "AKTİF TOPLAMI", b.aktif_toplam
    else:
        satirlar, bolumler = b.pasif, PASIF_BOLUM
        toplam_etiket, toplam = "PASİF TOPLAMI", b.pasif_toplam

    for d, baslik in bolumler.items():
        ds = [s for s in satirlar if s.ana[:1] == d]
        if not ds and not (taraf == "pasif" and d == "5"):
            continue
        _section(t, baslik)
        alt = 0.0
        for s in ds:
            _row(t, f"   {s.ana}   {s.ad}", s.tutar)
            alt += s.tutar
        if taraf == "pasif" and d == "5":
            _row(t, "   Dönem Net Kârı/Zararı", b.donem_kz, bold=True)
            alt += b.donem_kz
        _row(t, _ALT_TOPLAM_ETIKET[d], alt, bold=True, renk=SUBINK)

    _row(t, toplam_etiket, toplam, big=True, renk=NAVY)
    _fit_height(t)


def _panel(baslik: str, t: QTreeWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("panelCard")
    card.setStyleSheet(
        "QFrame#panelCard { background: %s; border: 1px solid #e3e8ef; border-radius: 12px; }"
        % PANEL_BG
    )
    card.setMinimumWidth(360)
    # Dikey Expanding: iki panel de en yüksek olanın boyuna uzar → başlıklar üstte hizalı
    # (kısa panel alttan boşluk alır; dikeyde ortalama yapılmaz — kullanıcı isteği).
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    lbl = QLabel(baslik)
    lbl.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: 800; background: transparent;")
    lay.addWidget(lbl)
    lay.addWidget(t)
    lay.addStretch(1)  # içeriği yukarı sabitle
    return card


def _kpi_card(baslik: str, deger: str, bg: str, vrenk: str) -> QFrame:
    card = QFrame()
    card.setObjectName("kpiCard")
    card.setStyleSheet(
        "QFrame#kpiCard { background: %s; border: 1px solid #e7ecf3; border-radius: 10px; }"
        % bg
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 11, 14, 11)
    lay.setSpacing(3)
    b = QLabel(baslik)
    b.setStyleSheet("color: #64748b; font-size: 11px; background: transparent;")
    v = QLabel(deger)
    v.setStyleSheet(f"color: {vrenk}; font-size: 18px; font-weight: 800; background: transparent;")
    lay.addWidget(b)
    lay.addWidget(v)
    return card


def build_bilanco_widget(b: Bilanco, firma: str = "") -> QWidget:
    """Bir Bilanço'dan, QScrollArea içine konacak yerel görünüm widget'ı üretir."""
    # Denge & dönem K/Z renkleri (HTML sürümüyle aynı mantık)
    if abs(b.fark) < 1.0:
        denge_txt, denge_bg, denge_vr = "✓ DENGEDE", "#e8f6ee", "#15803d"
    elif b.dengede:
        denge_txt, denge_bg, denge_vr = f"≈ %{b.denge_yuzde:.2f}", "#fdf3e0", "#b45309"
    else:
        denge_txt, denge_bg, denge_vr = "✗ FARK", "#fdecec", "#b91c1c"
    kz_bg, kz_vr = ("#e8f6ee", "#15803d") if b.donem_kz >= 0 else ("#fdecec", "#b91c1c")

    content = QWidget()
    content.setObjectName("bilancoContent")
    content.setStyleSheet("QWidget#bilancoContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(24, 18, 24, 24)
    root.setSpacing(14)

    # Başlık satırı
    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>ANINDA BİLANÇO &nbsp;·&nbsp; "
        f"{b.asof} tarihi itibarıyla{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>canlı/yönetim bilançosu — "
        f"kesin dönem sonucu için ay sonu kapanışı esastır</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    # KPI kartları
    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("TOPLAM AKTİF", tl(b.aktif_toplam), "#eef4ff", "#1d4ed8"))
    kpi.addWidget(_kpi_card("TOPLAM PASİF", tl(b.pasif_toplam), "#eef4ff", "#1d4ed8"))
    kpi.addWidget(_kpi_card("DÖNEM NET K/Z", tl(b.donem_kz), kz_bg, kz_vr))
    kpi.addWidget(_kpi_card("DENGE", denge_txt, denge_bg, denge_vr))
    root.addLayout(kpi)

    # AKTİF | PASİF panelleri — genişlik sınırlı kapsayıcıda eşit bölünür, ortalanır.
    # (Yan boşluklar paneli minimuma sıkıştırmasın diye kapsayıcı kullanılır.)
    t_aktif, t_pasif = _tree(), _tree()
    _doldur(t_aktif, b, "aktif")
    _doldur(t_pasif, b, "pasif")
    panel_row = QWidget()
    panel_row.setMaximumWidth(1280)
    panel_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    pr = QHBoxLayout(panel_row)
    pr.setContentsMargins(0, 0, 0, 0)
    pr.setSpacing(20)
    pr.addWidget(_panel("AKTİF (VARLIKLAR)", t_aktif), 1)
    pr.addWidget(_panel("PASİF (KAYNAKLAR)", t_pasif), 1)
    # panel_row genişliği doldurur (cap 1280); artan boşluk yan stretch'lere → ortalanır.
    outer = QHBoxLayout()
    outer.addStretch(1)
    outer.addWidget(panel_row, 12)
    outer.addStretch(1)
    root.addLayout(outer)
    root.addStretch(1)

    return content
