"""Reel Değer — PDF dışa aktarım."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.ortak import tr_sayi
from domain.reel_deger import ReelDegerAnalizi
from ui.pdf_ortak import (
    DARK,
    FONT,
    FONT_B,
    LINE,
    dipnot_ekle,
    letterhead_sade,
    pdf_ciz,
    pdf_doc,
    pdf_metin,
    sty_kpi,
    sty_row,
    sty_sec,
)

_BASLIK = "Reel Değer"


def _gun(v: float) -> str:
    return "—" if v < 0.05 else f"{tr_sayi(v, 0)} gün"


def _yuzde(v: float) -> str:
    return f"%{tr_sayi(v, 1)}"


def _ozet_tablo(a: ReelDegerAnalizi) -> Table:
    v = a.varsayim
    satirlar = [
        [Paragraph("VARSAYIM", sty_sec()), ""],
        [Paragraph("Paranın yıllık maliyeti", sty_row()), _yuzde(v.yillik_iskonto_yuzde)],
        [Paragraph("ALACAK", sty_sec()), ""],
        [Paragraph("Nominal tutar", sty_row()), tl(a.alacak.nominal)],
        [Paragraph("Bugünkü ekonomik değer", sty_kpi()), tl(a.alacak.bugunku_deger)],
        [Paragraph("Vade maliyeti", sty_row()), tl(a.alacak.vade_etkisi)],
        [Paragraph("Vadeye kalan (ortalama)", sty_row()), _gun(a.alacak.agirlikli_gun)],
        [Paragraph("BORÇ", sty_sec()), ""],
        [Paragraph("Nominal tutar", sty_row()), tl(a.borc.nominal)],
        [Paragraph("Bugünkü ekonomik değer", sty_kpi()), tl(a.borc.bugunku_deger)],
        [Paragraph("Vade avantajı", sty_row()), tl(a.borc.vade_etkisi)],
        [Paragraph("Vadeye kalan (ortalama)", sty_row()), _gun(a.borc.agirlikli_gun)],
        [Paragraph("NET POZİSYON", sty_sec()), ""],
        [Paragraph("Nominal", sty_row()), tl(a.nominal_net_pozisyon)],
        [Paragraph("Reel", sty_kpi()), tl(a.reel_net_pozisyon)],
        [Paragraph("Vade etkisi", sty_row()), tl(a.net_vade_etkisi)],
    ]
    t = Table(satirlar, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, -1), FONT_B),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ("FONTNAME", (0, 0), (0, -1), FONT),
    ]))
    return t


def _basabas_bloku(a: ReelDegerAnalizi, elems: list) -> None:
    elems.extend([Spacer(1, 10),
                  Paragraph("VADELİ SATIŞTA BAŞABAŞ FİYAT FARKI", sty_sec()), Spacer(1, 4)])
    rows = [[Paragraph(h, sty_sec()) for h in ("Vade", "Gereken fiyat farkı")]]
    rows.extend([Paragraph(f"{g} gün", sty_row()), _yuzde(y)] for g, y in a.basabas_merdiven)
    t = Table(rows, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, 1), (1, -1), FONT_B),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
    ]))
    elems.append(t)
    # Çapa DSO'dur, «vadeye kalan» değil: kalan gün tahsilat iyileştikçe düşüyor ve
    # başabaş tavsiyesini canlıda 5,5 kat eksik veriyordu.
    if a.basabas_olculdu:
        elems.extend([Spacer(1, 3), Paragraph(
            f"Ölçülen tahsil süreniz {_gun(a.dso or 0.0)}: vadeli fiyat peşin fiyatın "
            f"{_yuzde(a.basabas_kendi_vaden)} üstünde değilse vade farkını firma kendi "
            "kaynaklarından karşılamaktadır.", sty_row())])
    elif a.basabas_alt_sinir:
        elems.extend([Spacer(1, 3), Paragraph(
            f"Seçili dönem tahsil süresini ölçmeye yetmemektedir: tahsil süresi en az "
            f"{_gun(float(a.donem_gun))}, gereken fiyat farkı en az "
            f"{_yuzde(a.basabas_kendi_vaden)}.", sty_row())])


def _erime_bloku(kayitlar: list, elems: list, *, alacak: bool) -> None:
    if not kayitlar:
        return
    baslik = ("VADE MALİYETİNİ EN ÇOK BÜYÜTEN MÜŞTERİLER" if alacak
              else "EN ÇOK VADE AVANTAJI SAĞLAYAN SATICILAR")
    elems.extend([Spacer(1, 10), Paragraph(baslik, sty_sec()), Spacer(1, 4)])
    son = "Vade maliyeti" if alacak else "Vade avantajı"
    rows = [[Paragraph(h, sty_sec()) for h in ("Cari", "Nominal", "Vade", son)]]
    for c in kayitlar:
        rows.append([
            Paragraph(pdf_metin(c.unvan), sty_row()), tl(c.nominal),
            _gun(c.agirlikli_gun), tl(c.vade_etkisi),
        ])
    t = Table(rows, colWidths=[78 * mm, 32 * mm, 24 * mm, 36 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (3, 1), (3, -1), FONT_B),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
    ]))
    elems.append(t)
    elems.extend([Spacer(1, 3), Paragraph(
        "Sıralama bakiyeye değil vade etkisine göredir (tutar × bekleme süresi).",
        sty_row())])


def export_reel_deger_pdf(a: ReelDegerAnalizi, path: str | Path, *,
                          bas: str = "", bit: str = "", firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title=_BASLIK, firma=firma)
    elems: list = []
    letterhead_sade(elems, firma=firma, donem=f"{bit} itibarıyla · Tutarlar: TL")
    elems.append(_ozet_tablo(a))
    if a.gecikmis_alacak > 0.005:
        elems.extend([Spacer(1, 3), Paragraph(
            f"Vade maliyeti bir ALT SINIRDIR: vadesi geçmiş {tl(a.gecikmis_alacak)} bugün "
            "tahsil edilebilir kabul edilmiş, o tutarın bekleme süresi hesaba girmemiştir.",
            sty_row())])
    _basabas_bloku(a, elems)
    _erime_bloku(a.top_alacak_erime, elems, alacak=True)
    _erime_bloku(a.top_borc_erime, elems, alacak=False)
    dipnot_ekle(
        elems,
        belge="Vade etkisi / reel değer analizi",
        kaynak=("Canlı açık cari kalemler (vade kayıtlarına göre) · iskonto oranı kullanıcı "
                "varsayımıdır; nominal muhasebe tutarları değişmez"),
    )
    pdf_ciz(doc, elems, baslik=_BASLIK.upper())
    return out
