"""Yapay Zekâ Yorumu — PDF dışa aktarım (diğer raporlarla aynı kurumsal düzen)."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer

from domain.ai_yorum import AiYorum
from domain.ortak import tr_buyuk
from ui.ai_yorum_view import bolumlere_ayir
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    GRAY,
    dipnot_ekle,
    letterhead_sade,
    pdf_ciz,
    pdf_doc,
    sty_sec,
)

_POZ, _NEG = "#15803d", "#b91c1c"


def _madde_stili() -> ParagraphStyle:
    return ParagraphStyle(
        "ai_madde", fontName=FONT, fontSize=9, textColor=DARK, leading=13,
        leftIndent=10, bulletIndent=2, spaceAfter=2,
    )


def _paragraf_stili() -> ParagraphStyle:
    return ParagraphStyle("ai_par", fontName=FONT, fontSize=9, textColor=DARK, leading=13, spaceAfter=3)


def _kacir(metin: str) -> str:
    """Markdown **kalın** → <b>; gerisi XML için kaçışlanır (reportlab mini-HTML)."""
    guvenli = html.escape(metin)
    parcalar = guvenli.split("**")
    return "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(parcalar))


def export_ai_yorum_pdf(y: AiYorum, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Yapay Zekâ Yorumu", firma=firma or y.firma)
    elems: list = []
    letterhead_sade(elems, firma=firma or y.firma, bas=y.aralik_bas, bit=y.bit)

    par, madde = _paragraf_stili(), _madde_stili()
    for baslik, satirlar in bolumlere_ayir(y.metin):
        elems.append(Paragraph(html.escape(tr_buyuk(baslik)), sty_sec()))
        elems.append(Spacer(1, 3))
        for ham in satirlar:
            s = ham.strip()
            if s.startswith(("- ", "* ", "• ")):
                elems.append(Paragraph(_kacir(s[2:].strip()), madde, bulletText="•"))
            else:
                elems.append(Paragraph(_kacir(s), par))
        elems.append(Spacer(1, 8))

    elems.append(Paragraph(
        f"Model: {html.escape(y.model)} · Gönderilen veri: {html.escape(y.veri_ozeti)}",
        ParagraphStyle("ai_kaynak", fontName=FONT_B, fontSize=8, textColor=GRAY, leading=10),
    ))

    dipnot_ekle(
        elems,
        belge="Yapay zekâ tarafından üretilmiş yönetim yorumu; mali müşavir görüşü yerine geçmez",
        kaynak=f"Mikro ERP kayıtları · Yorum modeli: {y.model}",
    )
    pdf_ciz(doc, elems, baslik="YAPAY ZEKÂ YORUMU")
    return out
