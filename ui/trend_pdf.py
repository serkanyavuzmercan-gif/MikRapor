"""Mukayese & Oranlar — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.trend import MALIYET_EKSIK_UYARI, TrendRapor
from ui.mukayese_pdf import mukayese_notu, mukayese_tablosu
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    LINE,
    NAVY,
    dipnot_ekle,
    letterhead_sade,
    pdf_ciz,
    pdf_doc,
    sty_kpi,
    sty_row,
    sty_sec,
    sty_uyari,
)


def export_trend_pdf(tr: TrendRapor, path: str | Path, firma: str = "",
                     kapanislar: list | None = None) -> Path:
    out = Path(path)
    # SAYFA YATAY. Mukayese tablosu on yıla kadar sütun alabiliyor; dikey A4'te sütun
    # 11 mm'ye düşüp hücreler üst üste biniyordu (kullanıcı «pdf sığmıyor» dedi).
    # Genişlikler artık sabit milimetre değil, doc.width'ten pay alır — sayfa boyu
    # değişirse tablolar da onunla değişir.
    doc = pdf_doc(out, title="Mukayese & Oranlar", firma=firma, yatay=True)
    en = doc.width
    elems: list = []
    letterhead_sade(elems, firma=firma, bas=tr.bas, bit=tr.bit)

    elems.append(Paragraph("FİNANSAL ORANLAR", sty_sec()))
    elems.append(Spacer(1, 4))
    oran_rows = [[Paragraph(h, sty_sec()) for h in ("Oran", "Değer", "Açıklama")]]
    for o in tr.oranlar:
        oran_rows.append([
            Paragraph(o.ad, sty_kpi()),
            Paragraph(o.metin(), sty_row()),
            Paragraph(o.aciklama, sty_row()),
        ])
    ot = Table(oran_rows, colWidths=[52 * mm, 26 * mm, en - 78 * mm], repeatRows=1)
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
        [Paragraph("Stok" + (" ⚠" if tr.maliyet_eksik else ""), sty_row()), tl(tr.stok)],
    ]
    oz = Table(ozet, colWidths=[en - 50 * mm, 50 * mm])
    oz.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    elems.extend([oz, Spacer(1, 4)])
    # PDF çoğu zaman mali müşavire/bankaya gidiyor; şişik stoğun sebebi rakamın
    # yanında yazmazsa okuyan onu gerçek sanar.
    if tr.maliyet_eksik:
        elems.append(Paragraph(MALIYET_EKSIK_UYARI, sty_uyari()))
    elems.append(Spacer(1, 10))

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
            _th("Satış"),
            _th("Alış"),
            _th("Brüt"),
            _th("Nakit net"),
        ]]
        for a in tr.aylik:
            rows.append([
                _td(a.ay),
                _td(tl(a.satis)),
                _td(tl(a.alis)),
                _td(tl(a.brut)),
                _td(tl(a.nakit_net)),
            ])
        # Aylık trend dört tutar sütunu; kalan en eşit paylaşılır.
        tutar_en = (en - 30 * mm) / 4
        tt = Table(rows, colWidths=[30 * mm] + [tutar_en] * 4, repeatRows=1)
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

    tablo = mukayese_tablosu(kapanislar or [], en=en)
    if tablo is not None:
        elems.append(Paragraph("YILLAR ARASI MUKAYESE", sty_sec()))
        elems.append(Spacer(1, 4))
        elems.append(tablo)
        elems.append(mukayese_notu(kapanislar or []))

    dipnot_ekle(
        elems,
        belge="Trend ve finansal oran özeti",
        kaynak="Mikro GL mizan / cari hareketler · Hesap planı: TDHP",
        en=en,
    )
    pdf_ciz(doc, elems, baslik="MUKAYESE & ORANLAR")
    return out
