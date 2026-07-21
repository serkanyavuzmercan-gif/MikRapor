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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from domain.gelir_tablosu import GelirTablosu, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_pdf import DARK, FONT, FONT_B, GRAY, LINE, NAVY
from ui.pdf_ortak import dipnot_ekle, letterhead_sade, pdf_ciz


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
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=26 * mm, bottomMargin=22 * mm,
        title="Gelir Tablosu", author=firma or "MikRapor",
    )
    elems: list = []
    letterhead_sade(elems, firma=firma, bas=gt.bas, bit=gt.bit)
    # Maliyet eksik uyarısı yalnızca uygulama ekranında; PDF'e konmaz.
    elems.append(_govde(gt))

    # Marj özeti (dipnottan önce kısa KPI satırı)
    elems.append(Spacer(1, 8))
    ozet = (
        f"Brüt kâr marjı {yuzde(gt.brut_marj)} &nbsp;·&nbsp; "
        f"Faaliyet marjı {yuzde(gt.faaliyet_marj)} &nbsp;·&nbsp; "
        f"Net kâr marjı {yuzde(gt.net_marj)}"
    )
    elems.append(Paragraph(
        ozet,
        ParagraphStyle("oz", fontName=FONT, fontSize=8, textColor=GRAY, leading=10),
    ))

    dipnot_ekle(
        elems,
        belge="Yönetim amaçlı ara gelir tablosu",
        kaynak="Mikro GL mizan · Hesap planı: TDHP",
    )

    pdf_ciz(doc, elems, baslik="GELİR TABLOSU")
    return out
