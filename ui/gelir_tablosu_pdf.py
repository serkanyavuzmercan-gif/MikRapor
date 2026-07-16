"""
GELİR TABLOSU — PDF dışa aktarım (reportlab). Kurumsal mali tablo görünümü.

bilanco_pdf ile aynı letterhead/font düzenini paylaşır; tek sütun şelale gelir tablosu.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from domain.gelir_tablosu import GelirTablosu, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_pdf import DARK, FONT, FONT_B, GRAY, LINE, NAVY, _tr_tarih


def _govde(gt: GelirTablosu) -> Table:
    sty_sec = ParagraphStyle("sec", fontName=FONT_B, fontSize=8.5, textColor=NAVY, leading=12)
    sty_row = ParagraphStyle("row", fontName=FONT, fontSize=8.5, textColor=colors.HexColor("#333333"), leading=11)
    sty_sonuc = ParagraphStyle("son", fontName=FONT_B, fontSize=9, textColor=DARK, leading=12)

    data: list[list] = []
    cmds: list[tuple] = []
    r = 0
    for s in gt.satirlar:
        if s.tip == "bolum":
            data.append([Paragraph(s.etiket, sty_sec), ""])
            cmds += [("SPAN", (0, r), (1, r)), ("TOPPADDING", (0, r), (1, r), 7)]
        elif s.tip == "hesap":
            data.append([Paragraph(f"&nbsp;&nbsp;{s.etiket}", sty_row), tl(s.tutar or 0.0)])
        else:  # sonuc
            renk = DARK
            if s.etiket.startswith("DÖNEM NET"):
                renk = colors.HexColor("#15803d") if (s.tutar or 0) >= 0 else colors.HexColor("#b91c1c")
            data.append([Paragraph(s.etiket, ParagraphStyle("s", parent=sty_sonuc, textColor=renk)),
                         tl(s.tutar or 0.0)])
            cmds += [("LINEABOVE", (0, r), (1, r), 0.8, LINE), ("FONTNAME", (1, r), (1, r), FONT_B),
                     ("TEXTCOLOR", (1, r), (1, r), renk),
                     ("TOPPADDING", (0, r), (1, r), 4), ("BOTTOMPADDING", (0, r), (1, r), 4)]
        r += 1

    t = Table(data, colWidths=[130 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
    ] + cmds))
    return t


def export_gelir_tablosu_pdf(gt: GelirTablosu, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=14 * mm,
        title="Gelir Tablosu", author=firma or "MikRapor",
    )
    elems: list = []
    if firma:
        elems.append(Paragraph(
            firma, ParagraphStyle("firma", fontName=FONT_B, fontSize=15, textColor=DARK, leading=18)))
    elems.append(HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceBefore=3, spaceAfter=8))

    baslik_row = Table([[
        Paragraph("GELİR TABLOSU", ParagraphStyle("t", fontName=FONT_B, fontSize=13, textColor=DARK)),
        Paragraph(f"{_tr_tarih(gt.bas)} – {_tr_tarih(gt.bit)} Dönemi &nbsp;&nbsp;·&nbsp;&nbsp; Tutarlar: TL",
                  ParagraphStyle("d", fontName=FONT, fontSize=9, textColor=GRAY, alignment=2)),
    ]], colWidths=[70 * mm, 104 * mm])
    baslik_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elems.append(baslik_row)
    elems.append(Spacer(1, 8))

    if gt.maliyet_eksik:
        uyari = Table([[Paragraph(
            "⚠ Satışların Maliyeti (62) bu dönemde neredeyse sıfır — maliyet kapanışı yapılmamış "
            "olabilir. Brüt ve net kâr gerçekte olduğundan yüksek görünür.",
            ParagraphStyle("uy", fontName=FONT_B, fontSize=8, textColor=colors.HexColor("#8a1c1c"),
                           leading=10))]], colWidths=[174 * mm])
        uyari.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdecec")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e3a0a0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        elems.append(uyari)
        elems.append(Spacer(1, 8))

    elems.append(_govde(gt))

    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.4, color=LINE, spaceAfter=5))
    ozet = (f"Brüt kâr marjı {yuzde(gt.brut_marj)} &nbsp;·&nbsp; Faaliyet marjı {yuzde(gt.faaliyet_marj)} "
            f"&nbsp;·&nbsp; Net kâr marjı {yuzde(gt.net_marj)}")
    footer = Table([[
        Paragraph(ozet + "<br/>Yönetim amaçlı ara gelir tablosudur; kesinleşmiş resmî mali tablo "
                  "niteliği taşımaz.",
                  ParagraphStyle("ft", fontName=FONT, fontSize=7, textColor=GRAY, leading=9)),
        Paragraph("MikRapor", ParagraphStyle("br", fontName=FONT_B, fontSize=8,
                  textColor=colors.HexColor("#9aa6b6"), alignment=2)),
    ]], colWidths=[148 * mm, 26 * mm])
    footer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elems.append(footer)

    doc.build(elems)
    return out
