"""Tahsilat & Alacak — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.tahsilat_alacak import AGING_KOVALAR, TahsilatAlacak
from ui.pdf_ortak import DARK, FONT, FONT_B, LINE, letterhead, pdf_doc, sty_kpi, sty_row, sty_sec, tr_tarih


def export_tahsilat_alacak_pdf(ta: TahsilatAlacak, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Tahsilat & Alacak", firma=firma)
    elems: list = []
    letterhead(
        elems, firma=firma, baslik="TAHSİLAT & ALACAK",
        donem=f"{tr_tarih(ta.bas)} – {tr_tarih(ta.bit)} · Tutarlar: TL",
    )

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
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    elems.extend([t, Spacer(1, 8), Paragraph("ALACAK YAŞLANDIRMA", sty_sec()), Spacer(1, 3)])

    rows = [[Paragraph(k, sty_row()), tl(float(ta.alacak_aging.get(k, 0) or 0))] for k in AGING_KOVALAR]
    ta_tbl = Table(rows, colWidths=[120 * mm, 50 * mm])
    ta_tbl.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), FONT)]))
    elems.append(ta_tbl)

    elems.extend([Spacer(1, 8), Paragraph("BORÇ YAŞLANDIRMA", sty_sec()), Spacer(1, 3)])
    brows = [[Paragraph(k, sty_row()), tl(float(ta.borc_aging.get(k, 0) or 0))] for k in AGING_KOVALAR]
    bt = Table(brows, colWidths=[120 * mm, 50 * mm])
    bt.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), FONT)]))
    elems.append(bt)

    doc.build(elems)
    return out
