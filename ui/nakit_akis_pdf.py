"""Nakit Akış — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.nakit_akis import CIKIS_ETIKET, CIKIS_SIRA, GIRIS_ETIKET, GIRIS_SIRA, NakitAkis
from ui.pdf_ortak import DARK, FONT, FONT_B, LINE, letterhead, pdf_doc, sty_kpi, sty_row, sty_sec, tr_tarih


def export_nakit_akis_pdf(na: NakitAkis, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Nakit Akış", firma=firma)
    elems: list = []
    letterhead(
        elems, firma=firma, baslik="NAKİT AKIŞ",
        donem=f"{tr_tarih(na.bas)} – {tr_tarih(na.bit)} · Tutarlar: TL",
    )

    ozet = [
        [Paragraph("Açılış nakit", sty_row()), tl(na.acilis_nakit)],
        [Paragraph("Toplam giriş", sty_row()), tl(na.toplam_giris)],
        [Paragraph("Toplam çıkış", sty_row()), tl(na.toplam_cikis)],
        [Paragraph("Net akış", sty_kpi()), tl(na.net_akis)],
        [Paragraph("Kapanış nakit", sty_kpi()), tl(na.kapanis_nakit)],
    ]
    t = Table(ozet, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    elems.extend([t, Spacer(1, 8), Paragraph("GİRİŞLER", sty_sec()), Spacer(1, 3)])

    giris = []
    for k in GIRIS_SIRA:
        v = float(na.giris_kategori.get(k, 0) or 0)
        if abs(v) < 0.005:
            continue
        giris.append([Paragraph(GIRIS_ETIKET.get(k, k), sty_row()), tl(v)])
    if giris:
        tg = Table(giris, colWidths=[120 * mm, 50 * mm])
        tg.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), FONT)]))
        elems.append(tg)
    elems.extend([Spacer(1, 8), Paragraph("ÇIKIŞLAR", sty_sec()), Spacer(1, 3)])
    cikis = []
    for k in CIKIS_SIRA:
        v = float(na.cikis_kategori.get(k, 0) or 0)
        if abs(v) < 0.005:
            continue
        cikis.append([Paragraph(CIKIS_ETIKET.get(k, k), sty_row()), tl(v)])
    if cikis:
        tc = Table(cikis, colWidths=[120 * mm, 50 * mm])
        tc.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), FONT)]))
        elems.append(tc)

    doc.build(elems)
    return out
