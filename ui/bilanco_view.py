"""
Bilanço — yerel Qt görünümü (QTreeWidget panelleri + tipografi KPI şeridi).

Neden HTML değil: bilanço gövdesi önceden QTextBrowser içinde HTML idi, ama Qt'nin
zengin-metin motoru CSS `:hover` desteklemez — satır üstüne gelince vurgulama yapılamaz.
Bu yüzden gövde yerel widget'larla çizilir: AKTİF | PASİF iki `QTreeWidget` paneli.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import AKTIF_BOLUM, PASIF_BOLUM, Bilanco, tl
from ui.styles import (
    ACCENT,
    BAD,
    BORDER,
    FAINT,
    INK,
    MUTED,
    NAVY,
    OK,
    PAGE_BG,
    PANEL_BG,
    WARN,
)

# View'lar styles token'larını buradan da import edebilir (geriye uyumluluk)
__all__ = [
    "ACCENT",
    "FAINT",
    "MUTED",
    "NAVY",
    "PAGE_BG",
    "build_bilanco_widget",
    "_kpi_card",
    "_kpi_metric",
    "_panel",
    "_tree",
    "_row",
    "_section",
    "_fit_height",
]

_TREE_QSS = f"""
QTreeWidget {{
    background: #ffffff;
    alternate-background-color: #f5f8fc;
    border: 1px solid {BORDER};
    border-radius: 10px;
    outline: 0;
    font-size: 13px;
}}
QTreeWidget::item {{
    padding: 6px 4px;
    color: #374151;
    border-bottom: 1px solid #e6eaf1;
}}
QTreeWidget::item:hover {{
    background: #ccfbf1;
    color: #0f172a;
}}
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
    t.setAlternatingRowColors(True)
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
    if f.pointSizeF() > 0:
        f.setPointSizeF(f.pointSizeF() + artis)
    elif f.pixelSize() > 0:
        f.setPixelSize(f.pixelSize() + 1)


def _section(t: QTreeWidget, baslik: str, toplam: float | None = None) -> None:
    """Koyu lacivert dolu bölüm başlığı bar'ı; sağda (varsa) bölüm toplamı (mockup 2).

    QSS'li QTreeWidget'ta item arka planı ezildiği için başlık, gerçek bir navy
    widget (setItemWidget) ile çizilir — böylece dolu bar güvenilir görünür.
    """
    it = QTreeWidgetItem(["", ""])
    it.setFlags(Qt.ItemFlag.ItemIsEnabled)
    it.setSizeHint(0, QSize(0, 36))
    t.addTopLevelItem(it)
    it.setFirstColumnSpanned(True)

    bar = QWidget()
    bar.setObjectName("sectionBar")
    bar.setStyleSheet(f"QWidget#sectionBar {{ background: {NAVY}; }}")
    h = QHBoxLayout(bar)
    h.setContentsMargins(12, 0, 14, 0)
    h.setSpacing(8)
    sol = QLabel(baslik)
    sol.setStyleSheet(
        "color: #ffffff; font-size: 13px; font-weight: 800; "
        "letter-spacing: 0.2px; background: transparent;"
    )
    h.addWidget(sol)
    h.addStretch(1)
    if toplam is not None:
        sag = QLabel(tl(toplam))
        sag.setStyleSheet(
            "color: #ffffff; font-size: 13px; font-weight: 800; background: transparent;"
        )
        h.addWidget(sag)
    t.setItemWidget(it, 0, bar)


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
        alt = sum(s.tutar for s in ds)
        if taraf == "pasif" and d == "5":
            alt += b.donem_kz
        # Bölüm toplamı koyu lacivert başlık bar'ının sağında (mockup 2)
        _section(t, baslik, alt)
        for s in ds:
            _row(t, f"  ›   {s.ana}   {s.ad}", s.tutar)
        if taraf == "pasif" and d == "5":
            _row(t, "  ›   Dönem Net Kârı/Zararı", b.donem_kz, bold=True)

    _row(t, toplam_etiket, toplam, big=True, renk=NAVY)
    _fit_height(t)


def _panel(baslik: str, t: QTreeWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("panelCard")
    card.setStyleSheet(
        f"QFrame#panelCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; "
        f"border-radius: 12px; }}"
    )
    card.setMinimumWidth(280)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    lbl = QLabel(baslik)
    lbl.setStyleSheet(
        f"color: {ACCENT}; font-size: 14px; font-weight: 800; background: transparent;"
    )
    lay.addWidget(lbl)
    lay.addWidget(t)
    lay.addStretch(1)
    return card


def _kpi_card(baslik: str, deger: str, bg: str, vrenk: str) -> QFrame:
    """Klasik soft kart (diğer sekmeler için)."""
    card = QFrame()
    card.setObjectName("kpiCard")
    card.setStyleSheet(
        f"QFrame#kpiCard {{ background: {bg}; border: 1px solid {BORDER}; border-radius: 10px; }}"
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 11, 14, 11)
    lay.setSpacing(3)
    b = QLabel(baslik)
    b.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
    v = QLabel(deger)
    v.setStyleSheet(
        f"color: {vrenk}; font-size: 18px; font-weight: 800; background: transparent;"
    )
    lay.addWidget(b)
    lay.addWidget(v)
    return card


def _kpi_metric(baslik: str, deger: str, *, vrenk: str = INK) -> QWidget:
    """Tipografi KPI — ağır kart yok (Teal A bilanço şeridi)."""
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(2)
    b = QLabel(baslik)
    b.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")
    v = QLabel(deger)
    v.setStyleSheet(f"color: {vrenk}; font-size: 20px; font-weight: 800;")
    lay.addWidget(b)
    lay.addWidget(v)
    return w


def _kpi_divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setStyleSheet(f"color: {BORDER};")
    line.setFixedWidth(1)
    return line


def build_bilanco_widget(
    b: Bilanco, firma: str = "", on_yil_gec: Callable[[int], None] | None = None,
) -> QWidget:
    """Bir Bilanço'dan, QScrollArea içine konacak yerel görünüm widget'ı üretir.

    on_yil_gec verilirse, maliyet kapanışı eksik (açık yıl) uyarısına "geçen yıl
    kapanışına geç" düğmesi eklenir; tıklanınca on_yil_gec(hedef_yil) çağrılır.
    """
    # Fark tutarı DAİMA gösterilir — büyük mutlak fark küçük yüzdeyle gizlenmesin.
    if abs(b.fark) < 1.0:
        denge_txt, denge_vr = "Dengede", OK
    elif b.dengede:
        denge_txt, denge_vr = f"≈ {tl(b.fark)}", WARN
    else:
        denge_txt, denge_vr = f"Fark {tl(b.fark)}", BAD
    kz_vr = OK if b.donem_kz >= 0 else BAD

    content = QWidget()
    content.setObjectName("bilancoContent")
    content.setStyleSheet(f"QWidget#bilancoContent {{ background: {PAGE_BG}; }}")
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f"  ·  <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:12px; letter-spacing:0.3px;'>"
        f"ANINDA BİLANÇO  ·  {b.asof} tarihi itibarıyla{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>canlı/yönetim bilançosu — "
        f"kesin dönem sonucu için ay sonu kapanışı esastır</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, b.asof))

    # Maliyet kapanışı yapılmamışsa "Dönem Net Kârı" şişik görünür — uyar + geçen yıla geç.
    if b.maliyet_eksik:
        uy_box = QFrame()
        uy_box.setObjectName("maliyetUyari")
        uy_box.setStyleSheet(
            "QFrame#maliyetUyari { background: #fdf3e0; border: 1px solid #f0d090; "
            "border-radius: 8px; }"
        )
        ub = QVBoxLayout(uy_box)
        ub.setContentsMargins(12, 10, 12, 10)
        ub.setSpacing(8)
        uy = QLabel(
            "⚠  Satışların maliyeti (62) bu tarih itibarıyla ~0 — maliyet kapanışı henüz "
            "yapılmamış olabilir. Bu durumda aşağıdaki «Dönem Net Kârı» gerçekte olduğundan "
            "yüksek (şişik) görünür. Kesin sonuç için kapanmış bir yıla bakmak daha doğrudur."
        )
        uy.setWordWrap(True)
        uy.setStyleSheet("color: #8a5a00; font-size: 12px; background: transparent; border: none;")
        ub.addWidget(uy)
        if on_yil_gec is not None:
            try:
                hedef_yil = int(str(b.asof)[:4]) - 1
            except (ValueError, TypeError):
                hedef_yil = 0
            if hedef_yil > 0:
                brow = QHBoxLayout()
                brow.setContentsMargins(0, 0, 0, 0)
                btn = QPushButton(f"🔁  {hedef_yil} kapanışına geç")
                btn.setObjectName("yilGecBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.setStyleSheet(
                    "QPushButton#yilGecBtn { background: #8a5a00; color: #ffffff; border: none; "
                    "border-radius: 6px; padding: 7px 14px; font-size: 12px; font-weight: 700; } "
                    "QPushButton#yilGecBtn:hover { background: #a06a10; }"
                )
                btn.clicked.connect(lambda _=False, y=hedef_yil: on_yil_gec(y))
                brow.addWidget(btn)
                brow.addStretch(1)
                ub.addLayout(brow)
        root.addWidget(uy_box)

    # Tipografi KPI şeridi (kart yığını değil)
    strip = QFrame()
    strip.setObjectName("kpiStrip")
    strip.setStyleSheet(
        f"QFrame#kpiStrip {{ background: #ffffff; border: 1px solid {BORDER}; "
        f"border-radius: 12px; }}"
    )
    kpi = QHBoxLayout(strip)
    kpi.setContentsMargins(16, 14, 16, 14)
    kpi.setSpacing(0)
    kpi.addWidget(_kpi_metric("TOPLAM AKTİF", tl(b.aktif_toplam), vrenk=NAVY), 1)
    kpi.addWidget(_kpi_divider())
    kpi.addWidget(_kpi_metric("TOPLAM PASİF", tl(b.pasif_toplam), vrenk=NAVY), 1)
    kpi.addWidget(_kpi_divider())
    kpi.addWidget(_kpi_metric("DÖNEM NET K/Z", tl(b.donem_kz), vrenk=kz_vr), 1)
    kpi.addWidget(_kpi_divider())
    kpi.addWidget(_kpi_metric("DENGE", denge_txt, vrenk=denge_vr), 1)
    root.addWidget(strip)

    t_aktif, t_pasif = _tree(), _tree()
    _doldur(t_aktif, b, "aktif")
    _doldur(t_pasif, b, "pasif")
    panel_row = QWidget()
    panel_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    pr = QHBoxLayout(panel_row)
    pr.setContentsMargins(0, 0, 0, 0)
    pr.setSpacing(16)
    pr.addWidget(_panel("AKTİF (VARLIKLAR)", t_aktif), 1)
    pr.addWidget(_panel("PASİF (KAYNAKLAR)", t_pasif), 1)
    root.addWidget(panel_row, 1)

    return content
