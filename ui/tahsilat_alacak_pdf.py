"""Tahsilat & Alacak — PDF dışa aktarım (KPI + yaşlandırma barları + vade takvimi)."""

from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from domain.mizan_bilanco import tl
from domain.tahsilat_alacak import AGING_KOVALAR, VADE_KOVALAR, TahsilatAlacak
from ui.pdf_ortak import (
    ACCENT,
    DARK,
    FONT,
    FONT_B,
    GRAY,
    LINE,
    letterhead,
    pdf_doc,
    sty_row,
    sty_sec,
    tr_tarih,
)

# Uygulama ile aynı yaşlandırma paleti (yeşil → kırmızı)
_AGING_RENK = {
    AGING_KOVALAR[0]: colors.HexColor("#15803d"),
    AGING_KOVALAR[1]: colors.HexColor("#65a30d"),
    AGING_KOVALAR[2]: colors.HexColor("#d97706"),
    AGING_KOVALAR[3]: colors.HexColor("#ea580c"),
    AGING_KOVALAR[4]: colors.HexColor("#b91c1c"),
}
_POZ = colors.HexColor("#15803d")
_NEG = colors.HexColor("#b91c1c")
_FAINT = colors.HexColor("#9aa6b6")
_TRACK = colors.HexColor("#e8edf3")
_CARD_BG = colors.HexColor("#f8fafc")


def _sty(name: str, *, size: float = 8, bold: bool = False, color=DARK, align: int = 0, leading: float | None = None):
    return ParagraphStyle(
        name,
        fontName=FONT_B if bold else FONT,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=leading or (size + 2),
    )


def _kpi_kutu(baslik: str, deger: str, *, bg: colors.Color, fg: colors.Color) -> Table:
    t = Table(
        [
            [Paragraph(baslik, _sty("k_h", size=7, bold=True, color=GRAY))],
            [Paragraph(deger, _sty("k_v", size=10, bold=True, color=fg))],
        ],
        colWidths=[40 * mm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (0, -1), (0, -1), 7),
        ("TOPPADDING", (0, 1), (0, 1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _oran_bar(oran: float, renk: colors.Color, *, genislik: float = 48 * mm, yukseklik: float = 7) -> Drawing:
    """0..1 yatay bar — uygulama yaşlandırma çubuklarıyla aynı dil."""
    oran = max(0.0, min(1.0, oran))
    d = Drawing(genislik, yukseklik + 2)
    d.add(Rect(0, 1, genislik, yukseklik, fillColor=_TRACK, strokeColor=None, rx=3, ry=3))
    dolu = max(1.5, genislik * oran) if oran > 0.001 else 0
    if dolu > 0:
        d.add(Rect(0, 1, dolu, yukseklik, fillColor=renk, strokeColor=None, rx=3, ry=3))
    return d


def _yaslandirma_kart(baslik: str, aging: dict, toplam: float, gecikmis: float) -> Table:
    enb = max((float(aging.get(k, 0) or 0) for k in AGING_KOVALAR), default=0.0) or 1.0
    tbl_data: list = [[Paragraph(baslik, sty_sec()), "", ""]]
    for k in AGING_KOVALAR:
        v = float(aging.get(k, 0) or 0)
        renk = _AGING_RENK[k]
        tutar_renk = renk if v > 0.005 else _FAINT
        tbl_data.append([
            Paragraph(k, _sty("ya", size=8, color=colors.HexColor("#374151"))),
            _oran_bar(v / enb, renk),
            Paragraph(tl(v), _sty("yt", size=8, bold=v > 0.005, color=tutar_renk, align=2)),
        ])
    tot_idx = len(tbl_data)
    tbl_data.append([
        Paragraph("Toplam", _sty("ytot", size=8.5, bold=True)),
        "",
        Paragraph(tl(toplam), _sty("ytotv", size=8.5, bold=True, align=2)),
    ])
    if gecikmis > 0.005 and toplam > 0.005:
        oran = gecikmis / toplam * 100
        tbl_data.append([
            Paragraph(
                f"Gecikmiş: {tl(gecikmis)}  (%{oran:.0f})",
                _sty("yg", size=7.5, bold=True, color=_NEG),
            ),
            "",
            "",
        ])

    t = Table(tbl_data, colWidths=[30 * mm, 32 * mm, 20 * mm])
    cmds = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("LINEABOVE", (0, tot_idx), (-1, tot_idx), 0.5, LINE),
        ("TOPPADDING", (0, tot_idx), (-1, tot_idx), 5),
    ]
    for i in range(1, tot_idx):
        cmds.append(("LINEBELOW", (0, i), (-1, i), 0.25, colors.HexColor("#eef2f6")))
    if len(tbl_data) > tot_idx + 1:
        cmds.append(("SPAN", (0, tot_idx + 1), (-1, tot_idx + 1)))
    t.setStyle(TableStyle(cmds))
    return t


def _performans_kart(ta: TahsilatAlacak) -> Table:
    def gun(v: float | None) -> str:
        return "—" if v is None else f"{v:.0f} gün"

    def pct(v: float | None) -> str:
        return "—" if v is None else ("%" + f"{v:.0f}")

    orani = ta.tahsilat_orani
    oran_renk = _POZ if (orani or 0) >= 100 else (_NEG if orani is not None else DARK)

    satirlar = [
        ("Dönem Tahsilatı (müşteriden)", tl(ta.donem_tahsilat), _POZ, False),
        ("Dönem Kredili Satış", tl(ta.donem_satis), DARK, False),
        ("Tahsilat Oranı", pct(orani), oran_renk, True),
        ("Ort. Tahsilat Süresi (DSO)", gun(ta.dso), DARK, True),
        ("SEP", "", None, False),
        ("Dönem Ödemesi (satıcıya)", tl(ta.donem_odeme), _NEG, False),
        ("Dönem Alış", tl(ta.donem_alis), DARK, False),
        ("Ort. Ödeme Süresi (DPO)", gun(ta.dpo), DARK, True),
    ]

    data: list = [[Paragraph("TAHSİLAT & ÖDEME PERFORMANSI", sty_sec()), ""]]
    sep_rows: list[int] = []
    for ad, deger, renk, bold in satirlar:
        if ad == "SEP":
            sep_rows.append(len(data))
            data.append([Paragraph("&nbsp;", _sty("sep", size=4)), ""])
            continue
        data.append([
            Paragraph(ad, _sty("p_a", size=8, bold=bold, color=colors.HexColor("#374151"))),
            Paragraph(deger, _sty("p_d", size=8, bold=bold, color=renk or DARK, align=2)),
        ])

    not_txt = ""
    if ta.dso is not None and ta.dpo is not None:
        fark = ta.dpo - ta.dso
        not_txt = (
            f"Nakit döngüsü: tahsilat {ta.dso:.0f}g, ödeme {ta.dpo:.0f}g — "
            + ("satıcı bizi finanse ediyor." if fark >= 0 else "biz satıcıyı finanse ediyoruz.")
        )
        data.append([Paragraph(not_txt, _sty("p_n", size=7, color=_FAINT)), ""])

    t = Table(data, colWidths=[56 * mm, 28 * mm])
    cmds = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in sep_rows:
        cmds.append(("LINEABOVE", (0, i), (-1, i), 0.5, LINE))
        cmds.append(("TOPPADDING", (0, i), (-1, i), 4))
        cmds.append(("BOTTOMPADDING", (0, i), (-1, i), 2))
    if not_txt:
        cmds.append(("SPAN", (0, -1), (-1, -1)))
    t.setStyle(TableStyle(cmds))
    return t


def _vade_kart(ta: TahsilatAlacak) -> Table:
    nv = ta.net_vade()
    data: list = [[
        Paragraph("NET VADE TAKVİMİ", sty_sec()),
        Paragraph("Girecek", _sty("vh", size=7, bold=True, color=GRAY, align=2)),
        Paragraph("Çıkacak", _sty("vh", size=7, bold=True, color=GRAY, align=2)),
        Paragraph("Net", _sty("vh", size=7, bold=True, color=GRAY, align=2)),
    ]]
    for k in VADE_KOVALAR:
        a = float(ta.alacak_vade.get(k, 0) or 0)
        b = float(ta.borc_vade.get(k, 0) or 0)
        n = float(nv.get(k, 0) or 0)
        gecikmis = k == VADE_KOVALAR[0]
        data.append([
            Paragraph(k, _sty("vk", size=7.5, bold=gecikmis, color=_NEG if gecikmis else colors.HexColor("#374151"))),
            Paragraph(tl(a) if a > 0.005 else "—", _sty("va", size=7.5, color=_POZ if a > 0.005 else _FAINT, align=2)),
            Paragraph(tl(b) if b > 0.005 else "—", _sty("vb", size=7.5, color=_NEG if b > 0.005 else _FAINT, align=2)),
            Paragraph(
                ("+" if n >= 0 else "") + tl(n),
                _sty("vn", size=7.5, bold=True, color=_POZ if n >= 0 else _NEG, align=2),
            ),
        ])

    t = Table(data, colWidths=[32 * mm, 16 * mm, 16 * mm, 16 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    return t


def _top_kart(baslik: str, kayitlar: list, renk: colors.Color) -> Table | None:
    if not kayitlar:
        return None
    data: list = [[Paragraph(baslik, sty_sec()), ""]]
    for c in kayitlar[:5]:
        ad = (c.unvan or c.kod or "")[:36]
        data.append([
            Paragraph(ad, _sty("top_a", size=8, color=colors.HexColor("#374151"))),
            Paragraph(tl(c.net), _sty("top_v", size=8, bold=True, color=renk, align=2)),
        ])
    t = Table(data, colWidths=[56 * mm, 26 * mm])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def export_tahsilat_alacak_pdf(ta: TahsilatAlacak, path: str | Path, firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Tahsilat & Alacak", firma=firma)
    elems: list = []
    letterhead(
        elems, firma=firma, baslik="TAHSİLAT & ALACAK",
        donem=f"{tr_tarih(ta.bas)} – {tr_tarih(ta.bit)} · Tutarlar: TL",
    )

    # —— KPI şeridi (uygulama üst kartları) ——
    ag_bg = colors.HexColor("#fdecec") if ta.alacak_gecikmis > 0.005 else colors.HexColor("#e8f6ee")
    ag_fg = _NEG if ta.alacak_gecikmis > 0.005 else _POZ
    np_bg = colors.HexColor("#e8f6ee") if ta.net_pozisyon >= 0 else colors.HexColor("#fdecec")
    np_fg = _POZ if ta.net_pozisyon >= 0 else _NEG
    kpi = Table([[
        _kpi_kutu("TOPLAM ALACAK", tl(ta.alacak_toplam), bg=colors.HexColor("#ecfdf8"), fg=ACCENT),
        _kpi_kutu("GECİKMİŞ ALACAK", tl(ta.alacak_gecikmis), bg=ag_bg, fg=ag_fg),
        _kpi_kutu("TOPLAM BORÇ", tl(ta.borc_toplam), bg=colors.HexColor("#fdf3e0"), fg=colors.HexColor("#b45309")),
        _kpi_kutu("NET POZİSYON", tl(ta.net_pozisyon), bg=np_bg, fg=np_fg),
    ]], colWidths=[43.5 * mm, 43.5 * mm, 43.5 * mm, 43.5 * mm])
    kpi.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elems.extend([kpi, Spacer(1, 8)])

    # —— Yaşlandırma (yan yana, bar grafik) ——
    yas = Table([[
        _yaslandirma_kart("ALACAK YAŞLANDIRMA (müşteri)", ta.alacak_aging, ta.alacak_toplam, ta.alacak_gecikmis),
        _yaslandirma_kart("BORÇ YAŞLANDIRMA (satıcı)", ta.borc_aging, ta.borc_toplam, ta.borc_gecikmis),
    ]], colWidths=[86 * mm, 86 * mm])
    yas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 3),
        ("LEFTPADDING", (1, 0), (1, 0), 3),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    elems.extend([yas, Spacer(1, 8)])

    # —— Performans + vade takvimi ——
    alt = Table([[
        _performans_kart(ta),
        _vade_kart(ta),
    ]], colWidths=[90 * mm, 82 * mm])
    alt.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 3),
        ("LEFTPADDING", (1, 0), (1, 0), 3),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    elems.extend([alt, Spacer(1, 8)])

    # —— Top listeler ——
    top_a = _top_kart("EN ÇOK ALACAKLI MÜŞTERİLER", ta.top_alacak, ACCENT)
    top_b = _top_kart("EN ÇOK BORÇLU SATICILAR", ta.top_borc, colors.HexColor("#b45309"))
    if top_a or top_b:
        top = Table([[
            top_a or Paragraph("", sty_row()),
            top_b or Paragraph("", sty_row()),
        ]], colWidths=[86 * mm, 86 * mm])
        top.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 3),
            ("LEFTPADDING", (1, 0), (1, 0), 3),
        ]))
        elems.extend([top, Spacer(1, 6)])

    # —— Dipnot ——
    dip = Paragraph(
        "Cari hareketlerden türetilmiştir; resmi GL bilançosu değildir. "
        "Yaşlandırma vade tarihine göre FIFO açık kalemdir. Yönetim amaçlı özet.",
        _sty("dip", size=7, color=GRAY, leading=9),
    )
    elems.append(dip)

    doc.build(elems)
    return out
