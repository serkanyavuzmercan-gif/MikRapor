"""Yapay Zekâ Yorumu — PDF dışa aktarım (diğer raporlarla aynı kurumsal düzen)."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.ai_yorum import AiYorum, yillar_tablosu
from domain.ortak import tr_buyuk
from ui.ai_yorum_view import bolumlere_ayir
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    GRAY,
    LINE,
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


def _mukayese_tablosu(y: AiYorum) -> tuple[Table | None, bool]:
    """
    Ekrandaki deterministik mukayesenin PDF karşılığı — aynı kaynaktan, aynı satırlar.

    (tablo, sabit_satir_var_mi) döner; ikincisi altına uyarı notu koymak için.
    """
    yillar, bolumler = yillar_tablosu(y.kapanislar)
    if not yillar:
        return None, False

    data = [[""] + [str(yil) for yil in yillar] + [f"{yillar[0]}→{yillar[-1]}"]]
    cmds = [("FONTNAME", (0, 0), (-1, 0), FONT_B), ("TEXTCOLOR", (0, 0), (-1, 0), GRAY),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE)]
    r = 1
    for bolum in bolumler:
        if bolum.baslik:
            data.append([tr_buyuk(bolum.baslik)] + [""] * (len(yillar) + 1))
            cmds += [("FONTNAME", (0, r), (-1, r), FONT_B),
                     ("TEXTCOLOR", (0, r), (-1, r), "#0f766e"),
                     ("LINEABOVE", (0, r), (-1, r), 0.6, LINE),
                     ("TOPPADDING", (0, r), (-1, r), 5)]
            r += 1
        for satir in bolum.satirlar:
            data.append([satir.etiket + ("  ⚠" if satir.sabit else ""),
                         *satir.hucreler, satir.degisim])
            renk = GRAY if satir.iyi is None else (_POZ if satir.iyi else _NEG)
            cmds += [("TEXTCOLOR", (-1, r), (-1, r), renk),
                     ("FONTNAME", (-1, r), (-1, r), FONT_B)]
            # Negatif hücreler kırmızı — ekranla aynı okuma.
            for i, negatif in enumerate(satir.eksi):
                if negatif:
                    cmds.append(("TEXTCOLOR", (i + 1, r), (i + 1, r), _NEG))
            r += 1

    # Sayfa eni (A4 − kenar boşlukları) sütunlara paylaştırılır; «41,2 milyon» sığmalı.
    kullanilabilir = 174 * mm
    etiket_en = 48 * mm
    genislik = [etiket_en] + [(kullanilabilir - etiket_en) / (len(yillar) + 1)] * (len(yillar) + 1)
    t = Table(data, colWidths=genislik, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 1), (-2, -1), DARK),
    ] + cmds))
    return t, any(satir.sabit for b in bolumler for satir in b.satirlar)


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

    # Mukayese EN ALTTA: önce okunacak yorum, sonra dayanağı olan rakamlar.
    tablo, sabit_var = _mukayese_tablosu(y)
    if tablo is not None:
        elems.append(Paragraph("YILLAR ARASI MUKAYESE", sty_sec()))
        elems.append(Spacer(1, 3))
        elems.append(tablo)
        not_stili = ParagraphStyle(
            "ai_not", fontName=FONT, fontSize=7.4, textColor=GRAY, leading=10)
        if sabit_var:
            elems.append(Paragraph(
                "⚠ işaretli satırlar tüm yıllarda aynı: bu kalemler muhasebede "
                "güncellenmemiş olabilir; onlardan türeyen oranlara güvenmeyin.", not_stili))
        elems.append(Paragraph(
            "Tutarlar TL'dir; büyük rakamlar «bin / milyon / milyar» diye kısaltılmıştır. "
            "«—» o yıl için hesaplanamadı.", not_stili))
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
