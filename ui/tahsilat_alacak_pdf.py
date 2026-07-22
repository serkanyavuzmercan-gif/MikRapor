"""Alacak & Borç — PDF dışa aktarım.

Üstte klasik liste (özet + yaşlandırma satırları); altında alacak/borç bar grafikleri.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.tahsilat_alacak import AGING_KOVALAR, TahsilatAlacak
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    GRAY,
    LINE,
    dipnot_ekle,
    letterhead_sade,
    pdf_ciz,
    pdf_doc,
    sty_kpi,
    sty_row,
    sty_sec,
)

# Yeşil → kırmızı (uygulama yaşlandırma paleti)
_AGING_RENK = {
    AGING_KOVALAR[0]: colors.HexColor("#15803d"),
    AGING_KOVALAR[1]: colors.HexColor("#65a30d"),
    AGING_KOVALAR[2]: colors.HexColor("#d97706"),
    AGING_KOVALAR[3]: colors.HexColor("#ea580c"),
    AGING_KOVALAR[4]: colors.HexColor("#b91c1c"),
}
_TRACK = colors.HexColor("#e8edf3")


def _liste_stili() -> TableStyle:
    return TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("FONTNAME", (0, 0), (0, -1), FONT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])


def _yaslandirma_grafik(baslik: str, aging: dict) -> Drawing:
    """Liste altına yatay bar grafik (kova etiketi + çubuk + tutar)."""
    genislik = 170 * mm
    satir_h = 16
    ust = 18
    alt = 4
    n = len(AGING_KOVALAR)
    yukseklik = ust + n * satir_h + alt
    d = Drawing(genislik, yukseklik)

    d.add(String(0, yukseklik - 12, baslik, fontName=FONT_B, fontSize=9, fillColor=DARK))

    enb = max((float(aging.get(k, 0) or 0) for k in AGING_KOVALAR), default=0.0) or 1.0
    etiket_w = 52 * mm
    tutar_w = 38 * mm
    bar_x = etiket_w + 4
    bar_max = genislik - etiket_w - tutar_w - 10
    bar_h = 8

    for i, k in enumerate(AGING_KOVALAR):
        v = float(aging.get(k, 0) or 0)
        y = yukseklik - ust - (i + 1) * satir_h + 4
        renk = _AGING_RENK[k]
        d.add(String(0, y + 1, k, fontName=FONT, fontSize=8, fillColor=colors.HexColor("#374151")))
        d.add(Rect(bar_x, y, bar_max, bar_h, fillColor=_TRACK, strokeColor=None, rx=3, ry=3))
        if v > 0.005:
            dolu = max(2.0, bar_max * (v / enb))
            d.add(Rect(bar_x, y, dolu, bar_h, fillColor=renk, strokeColor=None, rx=3, ry=3))
        d.add(String(
            genislik, y + 1, tl(v),
            fontName=FONT_B if v > 0.005 else FONT,
            fontSize=8,
            fillColor=renk if v > 0.005 else GRAY,
            textAnchor="end",
        ))
    return d


def export_tahsilat_alacak_pdf(ta: TahsilatAlacak, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Alacak & Borç", firma=firma)
    elems: list = []
    letterhead_sade(elems, firma=firma, bas=ta.bas, bit=ta.bit)

    # —— Klasik özet listesi ——
    ozet = [
        [Paragraph("Cari sayısı", sty_row()), str(ta.cari_sayisi)],
        [Paragraph("Alacak toplam", sty_kpi()), tl(ta.alacak_toplam)],
        [Paragraph("Alacak gecikmiş", sty_row()), tl(ta.alacak_gecikmis)],
        [Paragraph("Borç toplam", sty_kpi()), tl(ta.borc_toplam)],
        [Paragraph("Borç gecikmiş", sty_row()), tl(ta.borc_gecikmis)],
        [Paragraph("Net pozisyon", sty_kpi()), tl(ta.net_pozisyon)],
    ]
    if ta.dso is not None:
        ozet.append([Paragraph("DSO", sty_row()), f"{ta.dso:.0f} gün"])
    if ta.dpo is not None:
        ozet.append([Paragraph("DPO", sty_row()), f"{ta.dpo:.0f} gün"])
    if ta.tahsilat_orani is not None:
        ozet.append([Paragraph("Tahsilat oranı", sty_row()), f"%{ta.tahsilat_orani:.1f}".replace(".", ",")])

    t = Table(ozet, colWidths=[120 * mm, 50 * mm])
    t.setStyle(_liste_stili())
    elems.extend([t, Spacer(1, 8), Paragraph("ALACAK YAŞLANDIRMA", sty_sec()), Spacer(1, 3)])

    rows = [[Paragraph(k, sty_row()), tl(float(ta.alacak_aging.get(k, 0) or 0))] for k in AGING_KOVALAR]
    ta_tbl = Table(rows, colWidths=[120 * mm, 50 * mm])
    ta_tbl.setStyle(_liste_stili())
    elems.append(ta_tbl)

    elems.extend([Spacer(1, 8), Paragraph("BORÇ YAŞLANDIRMA", sty_sec()), Spacer(1, 3)])
    brows = [[Paragraph(k, sty_row()), tl(float(ta.borc_aging.get(k, 0) or 0))] for k in AGING_KOVALAR]
    bt = Table(brows, colWidths=[120 * mm, 50 * mm])
    bt.setStyle(_liste_stili())
    elems.append(bt)

    # —— Listelerin altında bar grafikleri ——
    elems.extend([
        Spacer(1, 12),
        Paragraph("YAŞLANDIRMA GRAFİKLERİ", sty_sec()),
        Spacer(1, 6),
        _yaslandirma_grafik("Alacak yaşlandırma", ta.alacak_aging),
        Spacer(1, 8),
        _yaslandirma_grafik("Borç yaşlandırma", ta.borc_aging),
    ])

    dipnot_ekle(
        elems,
        belge="Yönetim amaçlı tahsilat ve alacak özeti",
        kaynak="Mikro cari hareketleri · Yaşlandırma: vade tarihine göre FIFO açık kalem",
    )

    pdf_ciz(doc, elems, baslik="ALACAK & BORÇ")
    return out
