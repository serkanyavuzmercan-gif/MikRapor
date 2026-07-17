"""Ortak PDF letterhead / font yardımcıları (reportlab)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
NAVY = colors.HexColor("#1f3a5f")
DARK = colors.HexColor("#1f2937")
GRAY = colors.HexColor("#6b7280")
LINE = colors.HexColor("#c9cfd8")
ACCENT = colors.HexColor("#0f766e")


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


def tr_tarih(asof: str) -> str:
    try:
        y, m, d = asof.split("-")
        return f"{d}.{m}.{y}"
    except Exception:  # noqa: BLE001
        return asof


def pdf_doc(path: Path, *, title: str, firma: str = "") -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title=title,
        author=firma or "MikRapor",
    )


def letterhead(elems: list, *, firma: str, baslik: str, donem: str) -> None:
    if firma:
        elems.append(Paragraph(
            firma,
            ParagraphStyle("firma", fontName=FONT_B, fontSize=15, textColor=DARK, leading=18),
        ))
    elems.append(HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceBefore=3, spaceAfter=8))
    elems.append(Paragraph(
        baslik,
        ParagraphStyle("t", fontName=FONT_B, fontSize=13, textColor=DARK, leading=16),
    ))
    elems.append(Paragraph(
        donem,
        ParagraphStyle("d", fontName=FONT, fontSize=9, textColor=GRAY, leading=12),
    ))
    elems.append(Spacer(1, 8))


def sty_row() -> ParagraphStyle:
    return ParagraphStyle("row", fontName=FONT, fontSize=8.5, textColor=colors.HexColor("#333333"), leading=11)


def sty_sec() -> ParagraphStyle:
    return ParagraphStyle("sec", fontName=FONT_B, fontSize=8.5, textColor=NAVY, leading=12)


def sty_kpi() -> ParagraphStyle:
    return ParagraphStyle("kpi", fontName=FONT_B, fontSize=9, textColor=DARK, leading=12)


def _uretim_zamani() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def kurumsal_dipnot(
    *,
    belge: str,
    kaynak: str = "Mikro ERP kayıtları · Hesap planı: TDHP",
    ek: str = "",
) -> list:
    """
    Tüm PDF’lerin altındaki kurumsal dipnot (Bilanço ile aynı dil).

    belge: kısa belge tanımı, örn. «yönetim amaçlı anlık bilanço»
    kaynak: veri kaynağı / yöntem satırı
    ek: niteliğe eklenecek ek cümle (opsiyonel)
    """
    sty = ParagraphStyle(
        "ft", fontName=FONT, fontSize=8, textColor=GRAY, leading=10.5, alignment=0,
    )
    sty_b = ParagraphStyle(
        "ftb", fontName=FONT_B, fontSize=8.5, textColor=colors.HexColor("#64748b"),
        leading=11, alignment=2,
    )

    nitelik = (
        f"<b>Belge niteliği:</b> {belge}. "
        "Kesinleşmiş yasal mali tablo veya e-defter çıktısı değildir. "
        "Mikro ERP genel muhasebe / cari kayıtlarından üretilmiştir."
    )
    if ek:
        nitelik += " " + ek

    kaynak_satir = (
        f"<b>Kaynak / yöntem:</b> {kaynak} "
        f"&nbsp;·&nbsp; Üretim: MikRapor · {_uretim_zamani()}"
    )
    sorumluluk = (
        "<b>Kullanım sınırı:</b> Bilgilendirme amaçlıdır; yatırım, kredi veya resmî beyan "
        "yerine geçmez. Doğruluk firma muhasebe kayıtlarına bağlıdır."
    )
    uretici = "Hidroteknik Yazılım — MikRapor ile üretilmiştir."

    t = Table(
        [
            [Paragraph(nitelik, sty)],
            [Paragraph(kaynak_satir, sty)],
            [Paragraph(sorumluluk, sty)],
            [Paragraph(uretici, sty_b)],
        ],
        colWidths=[174 * mm],
    )
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [t]


def dipnot_ekle(
    elems: list,
    *,
    belge: str,
    kaynak: str = "Mikro ERP kayıtları · Hesap planı: TDHP",
    ek: str = "",
) -> None:
    """İçeriğin altına çizgi + kurumsal dipnot ekler."""
    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.4, color=LINE, spaceAfter=4))
    elems.extend(kurumsal_dipnot(belge=belge, kaynak=kaynak, ek=ek))
