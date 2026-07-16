"""Ortak PDF letterhead / font yardımcıları (reportlab)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

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
