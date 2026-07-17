"""Nakit & Kârlılık — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.gercek_durum import GercekDurum
from domain.mizan_bilanco import tl
from ui.pdf_ortak import DARK, FONT, FONT_B, LINE, NAVY, dipnot_ekle, letterhead, pdf_doc, sty_kpi, sty_row, sty_sec, tr_tarih


def _th(metin: str, *, sag: bool = False) -> Paragraph:
    """Tablo başlığı — sayı sütunları sağa, Ay sola hizalı."""
    return Paragraph(
        metin,
        ParagraphStyle(
            "th",
            fontName=FONT_B,
            fontSize=8.5,
            textColor=NAVY,
            alignment=TA_RIGHT if sag else TA_LEFT,
            leading=11,
        ),
    )


def _td(metin: str, *, sag: bool = False, bold: bool = False) -> Paragraph:
    return Paragraph(
        metin,
        ParagraphStyle(
            "td",
            fontName=FONT_B if bold else FONT,
            fontSize=8.5,
            textColor=DARK,
            alignment=TA_RIGHT if sag else TA_LEFT,
            leading=11,
        ),
    )


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
        rows = [[
            _th("Ay"),
            _th("Satış", sag=True),
            _th("Alış", sag=True),
            _th("Brüt", sag=True),
            _th("Nakit net", sag=True),
        ]]
        for a in gd.trend:
            rows.append([
                _td(a.ay),
                _td(tl(a.satis), sag=True),
                _td(tl(a.alis), sag=True),
                _td(tl(a.brut), sag=True),
                _td(tl(a.nakit_net), sag=True, bold=True),
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

    dipnot_ekle(
        elems,
        belge="Yönetim amaçlı nakit ve kârlılık özeti",
        kaynak="Mikro stok / cari / banka hareketleri · Fiili marj mutabakatı",
    )
    doc.build(elems)
    return out
