"""Tahmin — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.tahmin import Tahmin
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


def export_tahmin_pdf(t: Tahmin, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Tahmin & Projeksiyon", firma=firma)
    elems: list = []
    v = t.varsayim
    letterhead_sade(
        elems, firma=firma,
        donem=f"{v.baslangic_ay} · {v.ufuk_ay} ay Dönemi · Tutarlar: TL",
    )

    ozet = [
        [Paragraph("VARSAYIMLAR", sty_sec()), ""],
        [Paragraph("Başlangıç nakit", sty_row()), tl(v.baslangic_nakit)],
        [Paragraph("Baz aylık ciro", sty_row()), tl(v.baz_ciro)],
        [Paragraph("Aylık büyüme", sty_row()), f"%{v.buyume_yuzde:.1f}".replace(".", ",")],
        [Paragraph("Brüt marj", sty_row()), f"%{v.marj_yuzde:.1f}".replace(".", ",")],
        [Paragraph("Aylık sabit gider", sty_row()), tl(v.sabit_gider)],
        [Paragraph("Açık kredi kartı borcu", sty_row()), tl(v.kart_borcu_acik)],
        [Paragraph("Kart borcu aylık ödeme oranı", sty_row()), f"%{v.kart_borcu_odeme_yuzde:.1f}".replace(".", ",")],
        [Paragraph("ÖZET", sty_sec()), ""],
        [Paragraph("Toplam ciro", sty_kpi()), tl(t.toplam_ciro)],
        [Paragraph("Toplam brüt kâr", sty_row()), tl(t.toplam_brut)],
        [Paragraph("Toplam net kâr", sty_row()), tl(t.toplam_net)],
        [Paragraph("Kart borcu ödemesi", sty_row()), tl(t.toplam_kart_borcu_odeme)],
        [Paragraph("Kalan kart borcu", sty_row()), tl(t.kalan_kart_borcu)],
        [Paragraph("Toplam net nakit etkisi", sty_row()), tl(t.toplam_net_nakit)],
        [Paragraph("Dönem sonu nakit", sty_kpi()), tl(t.son_nakit)],
        [Paragraph("En düşük nakit", sty_row()), f"{tl(t.en_dusuk_nakit)} ({t.en_dusuk_ay})"],
    ]
    tbl = Table(ozet, colWidths=[120 * mm, 50 * mm])
    tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ("FONTNAME", (0, 0), (0, -1), FONT),
    ]))
    elems.extend([tbl, Spacer(1, 10), Paragraph("AYLIK PROJEKSİYON", sty_sec()), Spacer(1, 4)])

    rows = [[Paragraph(h, sty_sec()) for h in ("Ay", "Ciro", "Brüt", "Kart borcu", "Net nakit", "Nakit")]]
    for a in t.aylar:
        rows.append([
            Paragraph(a.ay, sty_row()), tl(a.ciro), tl(a.brut_kar), tl(a.kart_borcu_odeme),
            tl(a.net_nakit), tl(a.nakit),
        ])
    at = Table(rows, colWidths=[22 * mm, 27 * mm, 27 * mm, 30 * mm, 32 * mm, 32 * mm])
    at.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
    ]))
    elems.append(at)
    dipnot_ekle(
        elems,
        belge="Tahmin / projeksiyon özeti",
        kaynak=("Kullanıcı varsayımları · canlı açık kart borcu · MikRapor projeksiyon modeli"),
    )
    pdf_ciz(doc, elems, baslik="TAHMİN & PROJEKSİYON")
    return out
