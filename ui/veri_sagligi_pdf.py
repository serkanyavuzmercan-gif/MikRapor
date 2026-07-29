"""
Veri Sağlığı — PDF dışa aktarım.

Bu PDF'in gideceği yer belli: MALİ MÜŞAVİR ya da muhasebeci. Kullanıcı «şu kayıtları
düzeltir misin» diye gönderiyor. O yüzden burada üslup diğer raporlardan farklı: rakam
tablosu değil, iş listesi. Her bulgunun altında düzeltilecek kayıtlar TEK TEK yazar —
«13 bozuk kayıt var» cümlesi, düzeltecek kişi için hiçbir şey ifade etmez.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from domain.veri_sagligi import KRITIK, UYARI, Bulgu, VeriSagligi
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

_EN = 174 * mm
_ETIKET_EN = 26 * mm

# Ekranda ilk 12 kayıt gösteriliyor; PDF'te SINIR YOK. Ekranı okunur tutmak için kırpmak
# başka, düzeltecek kişiye eksik liste göndermek başka.
_ONEM_RENK = {
    KRITIK: (colors.HexColor("#b91c1c"), colors.HexColor("#fef2f2")),
    UYARI: (colors.HexColor("#7a5b00"), colors.HexColor("#fff8e1")),
}
_ONEM_AD = {KRITIK: "KRİTİK", UYARI: "UYARI"}
_BILGI_RENK = (GRAY, colors.HexColor("#f5f7fa"))


def _sty(boyut: float, *, kalin: bool = False, renk=DARK, leading: float = 0.0):
    return ParagraphStyle(
        f"vs{boyut}{kalin}{renk}", fontName=FONT_B if kalin else FONT,
        fontSize=boyut, textColor=renk, leading=leading or boyut * 1.35)


def _bulgu_blogu(bulgu: Bulgu) -> KeepTogether:
    """Bir bulgu: önem şeridi + başlık + ölçüm + etkisi + ne yapmalı + kayıtlar."""
    yazi, arka = _ONEM_RENK.get(bulgu.onem, _BILGI_RENK)
    satirlar = [[
        Paragraph(_ONEM_AD.get(bulgu.onem, "NOT"), _sty(7.5, kalin=True, renk=yazi)),
        Paragraph(bulgu.baslik, _sty(11, kalin=True, renk=yazi)),
    ]]
    if bulgu.olcum:
        satirlar.append(["", Paragraph(bulgu.olcum, _sty(8.5, kalin=True, renk=yazi))])
    for etiket, metin in (("Etkisi", bulgu.etkisi), ("Ne yapmalı", bulgu.ne_yapmali)):
        satirlar.append(["", Paragraph(f"<b>{etiket}:</b> {metin}", _sty(8.5))])

    t = Table(satirlar, colWidths=[_ETIKET_EN, _EN - _ETIKET_EN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), arka),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, yazi),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 7),
    ]))
    parcalar: list = [t]
    if bulgu.kayitlar:
        parcalar += [Spacer(1, 3), _kayit_tablosu(bulgu.kayitlar)]
    parcalar.append(Spacer(1, 9))
    # KeepTogether: bulgu ile kayıtları sayfa arasında bölünmesin — kayıtsız kalan bir
    # «düzeltin» satırı, düzeltecek kişi için işe yaramaz.
    return KeepTogether(parcalar)


def _kayit_tablosu(kayitlar: list[str]) -> Table:
    """Düzeltilecek kayıtlar — PDF'te hepsi, kırpma yok."""
    basliklar = [[Paragraph("DÜZELTİLECEK KAYITLAR", sty_sec())]]
    satirlar = [[Paragraph(k, _sty(7.6, renk=DARK, leading=10))] for k in kayitlar]
    t = Table(basliklar + satirlar, colWidths=[_EN], repeatRows=1)
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
    ]))
    return t


def export_veri_sagligi_pdf(vs: VeriSagligi, path: str | Path,
                            firma: str = "") -> Path:
    out = Path(path)
    doc = pdf_doc(out, title="Veri Sağlığı", firma=firma)
    elems: list = []
    # Dönem yerine TARANAN ARALIK yazar: «temiz» sonucu, neye bakıldığı bilinmeden
    # sahte güven verir. Bu PDF müşavire gidiyor, kapsamı görmesi şart.
    letterhead_sade(elems, firma=firma,
                    donem=f"Taranan kayıtlar: {_gun(vs.bas)} – {_gun(vs.bit)}")

    elems.append(Paragraph(vs.ozet(), _sty(13, kalin=True)))
    elems.append(Spacer(1, 9))

    for bulgu in vs.bulgular:
        elems.append(_bulgu_blogu(bulgu))

    if vs.temiz and not vs.okunamayan:
        elems.append(Paragraph(
            "Rapor rakamlarını bozabilecek bir kayıt sorunu bulunamadı.",
            _sty(10, renk=colors.HexColor("#166534"))))
    if vs.okunamayan:
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(
            "<b>Kontrol edilemedi:</b> " + " · ".join(vs.okunamayan)
            + " — bağlantı ya da yetki sorunu olabilir. Bu alanlar «temiz» sayılmamalıdır.",
            _sty(8.5, renk=GRAY)))

    dipnot_ekle(
        elems,
        belge="Veri sağlığı kontrolü",
        kaynak="Mikro genel muhasebe (mizan) ve stok hareketleri · Hesap planı: TDHP",
        ek="Bulgular, rapor rakamlarını bozabilecek kayıt sorunlarıdır; "
           "muhasebe denetimi yerine geçmez.",
    )
    pdf_ciz(doc, elems, baslik="VERİ SAĞLIĞI")
    return out


def _gun(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if len(iso) == 10 else (iso or "—")
