"""Trend & Oranlar — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.trend import TrendRapor
from ui.pdf_ortak import DARK, FONT, FONT_B, LINE, NAVY, letterhead, pdf_doc, sty_kpi, sty_row, sty_sec, tr_tarih


def export_trend_pdf(tr: TrendRapor, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Trend & Oranlar", firma=firma)
    elems: list = []
    letterhead(
        elems, firma=firma, baslik="TREND & ORANLAR",
        donem=f"{tr_tarih(tr.bas)} – {tr_tarih(tr.bit)} · Bilanço {tr_tarih(tr.asof)} · Tutarlar: TL",
    )

    elems.append(Paragraph("FİNANSAL ORANLAR", sty_sec()))
    elems.append(Spacer(1, 4))
    oran_rows = [[Paragraph(h, sty_sec()) for h in ("Oran", "Değer", "Açıklama")]]
    for o in tr.oranlar:
        oran_rows.append([
            Paragraph(o.ad, sty_kpi()),
            Paragraph(o.metin(), sty_row()),
            Paragraph(o.aciklama, sty_row()),
        ])
    ot = Table(oran_rows, colWidths=[45 * mm, 25 * mm, 100 * mm])
    ot.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("TEXTCOLOR", (1, 1), (1, -1), DARK),
        ("FONTNAME", (1, 1), (1, -1), FONT_B),
    ]))
    elems.extend([ot, Spacer(1, 10)])

    ozet = [
        [Paragraph("BİLANÇO ÖZETİ", sty_sec()), ""],
        [Paragraph("Dönen varlıklar", sty_row()), tl(tr.donen)],
        [Paragraph("KVYK", sty_row()), tl(tr.kvyk)],
        [Paragraph("Özkaynak", sty_row()), tl(tr.ozkaynak)],
        [Paragraph("Nakit", sty_row()), tl(tr.nakit)],
        [Paragraph("Alacak", sty_row()), tl(tr.alacak)],
        [Paragraph("Stok", sty_row()), tl(tr.stok)],
    ]
    oz = Table(ozet, colWidths=[120 * mm, 50 * mm])
    oz.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    elems.extend([oz, Spacer(1, 10)])

    if tr.aylik:
        elems.append(Paragraph("AYLIK TREND", sty_sec()))
        elems.append(Spacer(1, 4))

        def _th(metin: str, *, sag: bool = False) -> Paragraph:
            return Paragraph(
                metin,
                ParagraphStyle(
                    "tr_th", fontName=FONT_B, fontSize=8.5, textColor=NAVY,
                    alignment=TA_RIGHT if sag else TA_LEFT, leading=11,
                ),
            )

        def _td(metin: str, *, sag: bool = False) -> Paragraph:
            return Paragraph(
                metin,
                ParagraphStyle(
                    "tr_td", fontName=FONT, fontSize=8.5, textColor=DARK,
                    alignment=TA_RIGHT if sag else TA_LEFT, leading=11,
                ),
            )

        rows = [[
            _th("Ay"),
            _th("Satış", sag=True),
            _th("Alış", sag=True),
            _th("Brüt", sag=True),
            _th("Nakit net", sag=True),
        ]]
        for a in tr.aylik:
            rows.append([
                _td(a.ay),
                _td(tl(a.satis), sag=True),
                _td(tl(a.alis), sag=True),
                _td(tl(a.brut), sag=True),
                _td(tl(a.nakit_net), sag=True),
            ])
        tt = Table(rows, colWidths=[28 * mm, 36 * mm, 36 * mm, 36 * mm, 38 * mm])
        tt.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ]))
        elems.append(tt)

    doc.build(elems)
    return out
