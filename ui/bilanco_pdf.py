"""
BİLANÇO — PDF dışa aktarım (reportlab). Kurumsal mali tablo görünümü.

Letterhead (firma adı + çizgi) · BİLANÇO başlığı + tarih · iki sütun AKTİF | PASİF ·
bölüm alt toplamları (Dönen/Duran/KV/UV/Özkaynak) · AKTİF TOPLAM = PASİF TOPLAM.
Denge, eşit toplamlarla zaten gösterilir (rozet/jargon yok). Türkçe için DejaVu fontu.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from domain.mizan_bilanco import AKTIF_BOLUM, PASIF_BOLUM, Bilanco, tl

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"

NAVY = colors.HexColor("#1f3a5f")
DARK = colors.HexColor("#1f2937")
GRAY = colors.HexColor("#6b7280")
LINE = colors.HexColor("#c9cfd8")

_ALT_TOPLAM_ETIKET = {
    "1": "Dönen Varlıklar Toplamı",
    "2": "Duran Varlıklar Toplamı",
    "3": "Kısa Vadeli Yab. Kaynaklar Toplamı",
    "4": "Uzun Vadeli Yab. Kaynaklar Toplamı",
    "5": "Özkaynaklar Toplamı",
}


def _register_fonts() -> None:
    global FONT, FONT_B
    try:
        import matplotlib
        base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        if (base / "DejaVuSans.ttf").is_file():
            pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
            FONT = "DejaVu"
        if (base / "DejaVuSans-Bold.ttf").is_file():
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(base / "DejaVuSans-Bold.ttf")))
            FONT_B = "DejaVu-Bold"
    except Exception:  # noqa: BLE001
        pass


_register_fonts()


def _tr_tarih(asof: str) -> str:
    try:
        y, m, d = asof.split("-")
        return f"{d}.{m}.{y}"
    except Exception:  # noqa: BLE001
        return asof


def _donem_metni(bas: str, bit: str) -> str:
    """PDF sağ üst dönem satırı — başlangıç–bitiş aralığı."""
    b, e = _tr_tarih(bas), _tr_tarih(bit)
    if not bas or bas == bit:
        return f"{e} tarihi itibarıyla &nbsp;&nbsp;·&nbsp;&nbsp; Tutarlar: TL"
    return f"{b} – {e} tarihleri arasındaki veriler &nbsp;&nbsp;·&nbsp;&nbsp; Tutarlar: TL"


def _side_table(b: Bilanco, taraf: str) -> Table:
    sty_col = ParagraphStyle("col", fontName=FONT_B, fontSize=9, textColor=colors.white, leading=11)
    sty_sec = ParagraphStyle("sec", fontName=FONT_B, fontSize=8, textColor=NAVY, leading=11)
    sty_row = ParagraphStyle("row", fontName=FONT, fontSize=7.5, textColor=colors.HexColor("#333333"), leading=9.5)
    sty_sub = ParagraphStyle("sub", fontName=FONT_B, fontSize=7.5, textColor=DARK, leading=10)

    if taraf == "aktif":
        col_title, satirlar, bolumler = "AKTİF (VARLIKLAR)", b.aktif, AKTIF_BOLUM
        toplam_etiket, toplam = "AKTİF TOPLAM", b.aktif_toplam
    else:
        col_title, satirlar, bolumler = "PASİF (KAYNAKLAR)", b.pasif, PASIF_BOLUM
        toplam_etiket, toplam = "PASİF TOPLAM", b.pasif_toplam

    data: list[list] = []
    cmds: list[tuple] = []
    r = 0

    data.append([Paragraph(col_title, sty_col), ""])
    cmds += [("SPAN", (0, r), (1, r)), ("BACKGROUND", (0, r), (1, r), NAVY),
             ("TOPPADDING", (0, r), (1, r), 5), ("BOTTOMPADDING", (0, r), (1, r), 5),
             ("LEFTPADDING", (0, r), (1, r), 6)]
    r += 1

    for d, baslik in bolumler.items():
        ds = [s for s in satirlar if s.ana[:1] == d]
        if not ds and not (taraf == "pasif" and d == "5"):
            continue
        data.append([Paragraph(baslik, sty_sec), ""])
        cmds += [("SPAN", (0, r), (1, r)), ("TOPPADDING", (0, r), (1, r), 7)]
        r += 1
        alt = 0.0
        for s in ds:
            data.append([Paragraph(f"{s.ana}&nbsp;&nbsp;{s.ad}", sty_row), tl(s.tutar)])
            alt += s.tutar
            r += 1
        if taraf == "pasif" and d == "5":
            data.append([Paragraph("Dönem Net Kârı/Zararı", sty_row), tl(b.donem_kz)])
            alt += b.donem_kz
            r += 1
        data.append([Paragraph(_ALT_TOPLAM_ETIKET[d], sty_sub), tl(alt)])
        cmds += [("LINEABOVE", (0, r), (1, r), 0.4, LINE), ("FONTNAME", (1, r), (1, r), FONT_B),
                 ("TOPPADDING", (0, r), (1, r), 3), ("BOTTOMPADDING", (0, r), (1, r), 4)]
        r += 1

    data.append([Paragraph(toplam_etiket, ParagraphStyle("tot", fontName=FONT_B, fontSize=9.5, textColor=DARK)), tl(toplam)])
    cmds += [("LINEABOVE", (0, r), (1, r), 1.3, DARK), ("FONTNAME", (1, r), (1, r), FONT_B),
             ("FONTSIZE", (1, r), (1, r), 9.5), ("TOPPADDING", (0, r), (1, r), 4)]

    t = Table(data, colWidths=[60 * mm, 28 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
    ] + cmds))
    return t


def export_bilanco_pdf(
    bilanco: Bilanco,
    path: str | Path,
    firma: str = "",
    *,
    bas: str = "",
    bit: str = "",
) -> Path:
    out = Path(path)
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=14 * mm,
        title="Bilanço", author=firma or "MikRapor",
    )
    elems: list = []

    # Letterhead — firma adı + ince çizgi
    if firma:
        elems.append(Paragraph(
            firma, ParagraphStyle("firma", fontName=FONT_B, fontSize=15, textColor=DARK, leading=18)))
    elems.append(HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceBefore=3, spaceAfter=8))

    # Başlık satırı: BİLANÇO  ·  dönem (sağda) — chrome’daki başlangıç–bitiş
    donem_bas = (bas or "").strip() or bilanco.asof
    donem_bit = (bit or "").strip() or bilanco.asof
    baslik_row = Table([[
        Paragraph("BİLANÇO", ParagraphStyle("t", fontName=FONT_B, fontSize=13, textColor=DARK)),
        Paragraph(
            _donem_metni(donem_bas, donem_bit),
            ParagraphStyle("d", fontName=FONT, fontSize=9, textColor=GRAY, alignment=2),
        ),
    ]], colWidths=[50 * mm, 126 * mm])
    baslik_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elems.append(baslik_row)
    elems.append(Spacer(1, 8))

    # Gövde: AKTİF | PASİF yan yana
    body = Table([[_side_table(bilanco, "aktif"), _side_table(bilanco, "pasif")]],
                 colWidths=[90 * mm, 90 * mm])
    body.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 6)]))
    elems.append(body)

    # Dipnot — profesyonel, ölçülü
    elems.append(Spacer(1, 12))
    elems.append(HRFlowable(width="100%", thickness=0.4, color=LINE, spaceAfter=5))
    not_metni = "Yönetim amaçlı ara bilançodur; kesinleşmiş resmî mali tablo niteliği taşımaz."
    if abs(bilanco.fark) >= 1.0:
        not_metni += f" Aktif–Pasif farkı ({tl(bilanco.fark)}) dönem-içi maliyet kapanışından kaynaklanmaktadır."
    footer = Table([[
        Paragraph(not_metni, ParagraphStyle("ft", fontName=FONT, fontSize=7, textColor=GRAY, leading=9)),
        Paragraph("MikRapor", ParagraphStyle("br", fontName=FONT_B, fontSize=8, textColor=colors.HexColor("#9aa6b6"), alignment=2)),
    ]], colWidths=[150 * mm, 26 * mm])
    footer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elems.append(footer)

    doc.build(elems)
    return out
