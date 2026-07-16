"""Nakit & Kârlılık — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.gercek_durum import GercekDurum
from domain.mizan_bilanco import tl
from ui.pdf_ortak import DARK, FONT, FONT_B, LINE, letterhead, pdf_doc, sty_kpi, sty_row, sty_sec, tr_tarih


def export_gercek_durum_pdf(gd: GercekDurum, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Nakit & Kârlılık", firma=firma)
    elems: list = []
    letterhead(
        elems, firma=firma, baslik="NAKİT & KÂRLILIK",
        donem=f"{tr_tarih(gd.bas)} – {tr_tarih(gd.bit)} · Tutarlar: TL",
    )

    data = [
        [Paragraph("ÖZET", sty_sec()), ""],
        [Paragraph("Fiili satış", sty_row()), tl(gd.gercek_satis)],
        [Paragraph("Fiili alış / SMM", sty_row()), tl(gd.gercek_alis)],
        [Paragraph("Fiili brüt kâr", sty_kpi()), tl(gd.gercek_brut_kar)],
        [Paragraph("Fiili brüt marj", sty_kpi()), f"%{gd.gercek_brut_marj:.1f}".replace(".", ",")],
        [Paragraph("Nakit giren", sty_row()), tl(gd.nakit_giren)],
        [Paragraph("Nakit çıkan", sty_row()), tl(gd.nakit_cikan)],
        [Paragraph("Nakit net", sty_kpi()), tl(gd.nakit_net)],
        [Paragraph("Nakit mevcut", sty_row()), tl(gd.nakit_mevcut)],
        [Paragraph("Alacak", sty_row()), tl(gd.alacak)],
        [Paragraph("Borç", sty_row()), tl(gd.borc)],
        [Paragraph("Net işletme sermayesi", sty_kpi()), tl(gd.net_isletme_sermayesi)],
    ]
    if gd.resmi_brut_marj is not None:
        data += [
            [Paragraph("MUTABAKAT", sty_sec()), ""],
            [Paragraph("Resmi brüt marj", sty_row()), f"%{gd.resmi_brut_marj:.1f}".replace(".", ",")],
            [Paragraph("Marj farkı (fiili−resmi)", sty_row()),
             f"%{(gd.marj_farki or 0):.1f}".replace(".", ",")],
        ]

    t = Table(data, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 10))

    if gd.trend:
        elems.append(Paragraph("AYLIK TREND", sty_sec()))
        elems.append(Spacer(1, 4))
        rows = [[Paragraph(h, sty_sec()) for h in ("Ay", "Satış", "Alış", "Brüt", "Nakit net")]]
        for a in gd.trend:
            rows.append([
                Paragraph(a.ay, sty_row()), tl(a.satis), tl(a.alis), tl(a.brut), tl(a.nakit_net),
            ])
        tt = Table(rows, colWidths=[28 * mm, 32 * mm, 32 * mm, 32 * mm, 36 * mm])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ]))
        elems.append(tt)

    doc.build(elems)
    return out
