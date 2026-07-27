"""
Yıllar arası mukayese tablosu — paylaşılan PDF üreticisi.

Trend & Oranlar PDF'i bunu basar; ekrandaki tabloyla (ui/mukayese_view.py) aynı
kaynaktan, aynı satırlarla.
"""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle

from domain.ai_yorum import YilKapanis, yillar_tablosu
from domain.ortak import tr_buyuk
from ui.pdf_ortak import DARK, FONT, FONT_B, GRAY, LINE

_POZ, _NEG = "#15803d", "#b91c1c"


def mukayese_tablosu(kapanislar: list[YilKapanis]) -> tuple[Table | None, bool]:
    """
    Ekrandaki deterministik mukayesenin PDF karşılığı — aynı kaynaktan, aynı satırlar.

    (tablo, sabit_satir_var_mi) döner; ikincisi altına uyarı notu koymak için.
    """
    yillar, bolumler = yillar_tablosu(kapanislar)
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


def mukayese_notu(sabit_var: bool) -> Paragraph:
    """Tablo altı açıklama; sabit satır varsa uyarıyla başlar."""
    stil = ParagraphStyle("mk_not", fontName=FONT, fontSize=7.4, textColor=GRAY, leading=10)
    metin = ("Alacak, borç ve nakit ilgili sekmelerin canlı kaynağından gelir; stok, "
             "özkaynak ve aktif mizandan. Tutarlar TL'dir; büyük rakamlar «bin / milyon "
             "/ milyar» diye kısaltılmıştır. «—» o yıl için hesaplanamadı.")
    if sabit_var:
        metin = ("⚠ işaretli satırlar tüm yıllarda aynı: bu kalemler muhasebede "
                 "güncellenmemiş olabilir; onlardan türeyen oranlara güvenmeyin. ") + metin
    return Paragraph(metin, stil)
