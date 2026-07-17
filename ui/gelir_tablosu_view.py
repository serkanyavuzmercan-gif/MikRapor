"""
Gelir Tablosu — yerel Qt görünümü (tek sütun şelale + KPI kartları).

bilanco_view'ın ortak yardımcılarını (tree/satır/KPI/panel + hover + zebra) yeniden kullanır;
gelir tablosu tek sütunlu şelale olduğu için ayrı bir düzenleyici. Veri modeli GelirTablosu.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from domain.gelir_tablosu import GelirTablosu, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_view import (
    FAINT,
    MUTED,
    NAVY,
    PAGE_BG,
    _fit_height,
    _kpi_card,
    _panel,
    _row,
    _section,
    _tree,
)
from ui.styles import ACCENT, PRIMARY_SOFT


def _doldur(t, gt: GelirTablosu) -> None:
    for s in gt.satirlar:
        if s.tip == "bolum":
            _section(t, s.etiket)
        elif s.tip == "hesap":
            _row(t, f"   {s.etiket}", s.tutar or 0.0)
        else:  # sonuc — yürüyen ara/nihai sonuç (vurgulu)
            if s.etiket.startswith("DÖNEM NET"):
                renk = "#15803d" if (s.tutar or 0) >= 0 else "#b91c1c"
                _row(t, s.etiket, s.tutar or 0.0, big=True, renk=renk)
            else:
                _row(t, s.etiket, s.tutar or 0.0, bold=True, renk=NAVY)
    _fit_height(t)


def _kpi_marj(baslik: str, tutar: float, marj: float, bg: str, vrenk: str):
    return _kpi_card(f"{baslik}  ·  {yuzde(marj)}", tl(tutar), bg, vrenk)


def build_gelir_tablosu_widget(gt: GelirTablosu, firma: str = "") -> QWidget:
    """Bir GelirTablosu'ndan, QScrollArea içine konacak yerel görünüm üretir."""
    nk_bg, nk_vr = ("#e8f6ee", "#15803d") if gt.net_kar >= 0 else ("#fdecec", "#b91c1c")

    content = QWidget()
    content.setObjectName("gtContent")
    content.setStyleSheet("QWidget#gtContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>GELİR TABLOSU &nbsp;·&nbsp; "
        f"{gt.bas} → {gt.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Dönem Net Kârı, bilançodaki "
        f"«Dönem Net Kârı» ile birebir tutar (aynı 6xx hesaplarından) — yerleşik mutabakat.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    root.addWidget(head)

    if gt.maliyet_eksik:
        uyari = QLabel(
            "⚠ <b>Satışların Maliyeti (62) bu dönemde neredeyse sıfır.</b> Mal satan bir "
            "işletmeyseniz <b>maliyet kapanışı henüz yapılmamış</b> demektir; brüt/net kâr "
            "GERÇEKTE OLDUĞUNDAN ÇOK YÜKSEK görünür. Maliyet kapanışı yapılmış (kapatılmış) "
            "bir dönem seçin ya da Mikro'da maliyet kapanışından sonra bakın."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdecec; border: 1px solid #f3c0c0; border-radius: 8px; "
            "color: #8a1c1c; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("NET SATIŞLAR", tl(gt.net_satislar), PRIMARY_SOFT, ACCENT))
    kpi.addWidget(_kpi_marj("BRÜT KÂR", gt.brut_kar, gt.brut_marj, PRIMARY_SOFT, ACCENT))
    kpi.addWidget(_kpi_marj("FAALİYET KÂRI", gt.faaliyet_kari, gt.faaliyet_marj, PRIMARY_SOFT, ACCENT))
    kpi.addWidget(_kpi_marj("DÖNEM NET KÂRI", gt.net_kar, gt.net_marj, nk_bg, nk_vr))
    root.addLayout(kpi)

    t = _tree()
    t.setColumnWidth(1, 160)
    _doldur(t, gt)
    panel = _panel("GELİR TABLOSU (Kâr/Zarar)", t)
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    root.addWidget(panel, 1)
    return content
