"""Nakit & Kârlılık — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle

from domain.gercek_durum import GercekDurum
from domain.mizan_bilanco import tl
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    LINE,
    dipnot_ekle,
    letterhead_sade,
    pdf_ciz,
    pdf_doc,
    sty_kpi,
    sty_row,
    sty_sec,
)


def export_gercek_durum_pdf(gd: GercekDurum, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Nakit & Kârlılık", firma=firma)
    elems: list = []
    letterhead_sade(elems, firma=firma, bas=gd.bas, bit=gd.bit)

    def _yuz(v: float) -> str:
        return f"%{v:.1f}".replace(".", ",")

    # OPERASYONEL KÂRLILIK — fiili kârlılık (stok hareketinden). Nakit akışı burada
    # tekrar edilmez (Nakit Akış tab'ının PDF'i ayrı); işletme sermayesi sentezi kalır.
    data = [
        [Paragraph("OPERASYONEL KÂRLILIK  (stok hareketinden)", sty_sec()), ""],
        [Paragraph("Fiili satış", sty_row()), tl(gd.gercek_satis)],
        [Paragraph("Fiili alış (−)", sty_row()), tl(-gd.gercek_alis)],
        [Paragraph("Fiili brüt kâr", sty_kpi()), tl(gd.gercek_brut_kar)],
        [Paragraph("Fiili brüt marj", sty_kpi()), _yuz(gd.gercek_brut_marj)],
        [Paragraph("İŞLETME SERMAYESİ  (günlük işi çevirecek net kaynak)", sty_sec()), ""],
        [Paragraph("Nakit (banka + kasa)", sty_row()), tl(gd.nakit_mevcut)],
        [Paragraph("Tahsil edilecek (net alacak)", sty_row()),
         tl(gd.alacak - gd.musteri_avans)],
        [Paragraph("Ödenecek (net borç) (−)", sty_row()),
         tl(-(gd.borc - gd.satici_avans))],
        [Paragraph("Net işletme sermayesi", sty_kpi()), tl(gd.net_isletme_sermayesi)],
    ]
    if gd.resmi_brut_marj is not None:
        data += [
            [Paragraph("RESMİ vs FİİLİ  (mutabakat)", sty_sec()), ""],
            [Paragraph("Resmi brüt marj", sty_row()), _yuz(gd.resmi_brut_marj)],
            [Paragraph("Fiili brüt marj", sty_row()), _yuz(gd.gercek_brut_marj)],
            [Paragraph("Marj farkı (fiili − resmi)", sty_kpi()), _yuz(gd.marj_farki or 0)],
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

    dipnot_ekle(
        elems,
        metin=(
            "Bu belge, Mikro ERP verilerinden üretilmiş yönetimsel bir kârlılık ve işletme "
            "sermayesi özetidir. Kesinleşmiş yasal mali tablo niteliği taşımaz. Yalnızca "
            "bilgilendirme amaçlıdır; resmî beyan, kredi veya yatırım aracı olarak "
            "kullanılamaz. Bilgiler mevcut muhasebe kayıtlarına dayanır."
        ),
    )
    pdf_ciz(doc, elems, baslik="NAKİT & KÂRLILIK")
    return out
