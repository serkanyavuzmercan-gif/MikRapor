"""
Yıllar arası mukayese tablosu — paylaşılan PDF üreticisi.

Mukayese & Oranlar PDF'i bunu basar; ekrandaki tabloyla (ui/mukayese_view.py) aynı
kaynaktan, aynı satırlarla.
"""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle

from domain.ai_yorum import YilKapanis, degisim_basligi, ortak_pencere, yillar_tablosu
from domain.ortak import tr_buyuk
from ui.pdf_ortak import DARK, FONT, FONT_B, GRAY, LINE

_POZ, _NEG = "#15803d", "#b91c1c"

# SÜTUN GENİŞLİĞİ EŞİT PAYLAŞTIRILMAZ. Eskiden etiket dışındaki her şey eşit bölünüyordu;
# on yıl istendiğinde sütun 11 mm'ye düşüyor, «41,2 milyon» (15,4 mm) ve «+310,89 puan»
# (20,5 mm kalın) komşu hücrenin üstüne biniyordu — kullanıcı «pdf sığmıyor» dedi.
# Sayfa yataya çevrildi ve genişlikler ROLE GÖRE verildi: değişim sütunu en uzun metni
# taşır, yıl sütunları kalanı paylaşır. Dar kalırsa yazı küçülür, taşmaz.
_ETIKET_EN = 50 * mm
_DEGISIM_EN = 28 * mm      # «+310,89 puan» kalın sığmalı
_ASGARI_ETIKET = 34 * mm
_ASGARI_DEGISIM = 22 * mm
_ASGARI_YIL = 15 * mm
_DAR_YIL = 17 * mm         # bunun altında yazı küçülür
_PADDING = 2               # nokta; dar sütunda 6+6 fazla yer yiyordu


def _genislikler(en: float, yil_sayisi: int) -> tuple[list[float], float]:
    """[etiket, yıl…, değişim] genişlikleri; ikinci değer yıl sütununun eni."""
    etiket, degisim = _ETIKET_EN, _DEGISIM_EN
    yil = (en - etiket - degisim) / yil_sayisi
    if yil < _ASGARI_YIL:
        # Önce etiket ve değişimden kısılır: rakam sütunu okunmazsa tablo işe yaramaz.
        etiket, degisim = _ASGARI_ETIKET, _ASGARI_DEGISIM
        yil = (en - etiket - degisim) / yil_sayisi
    return [etiket] + [yil] * yil_sayisi + [degisim], yil


def yazi_boyu(yil_en: float) -> float:
    """Dar sütunda punto küçülür — taşmaktansa küçük yazmak yeğdir."""
    return 7.4 if yil_en >= _DAR_YIL else 6.5


def mukayese_tablosu(kapanislar: list[YilKapanis], *,
                     en: float = 174 * mm) -> Table | None:
    """Ekrandaki deterministik mukayesenin PDF karşılığı — aynı kaynaktan, aynı satırlar."""
    yillar, bolumler = yillar_tablosu(kapanislar)
    if not yillar:
        return None

    # Başlık gerçek pencereyi yazar: «2025 (28.07–31.12)». Sütunlar farklı uzunlukta
    # olabilir; PDF bankaya/müşavire gittiğinde bunun görünmemesi yanlış okumaya yol açar.
    ortak = ortak_pencere(kapanislar)

    def _bas(yil: int) -> str:
        if ortak:                   # hepsi aynı pencere → başlıkta yalnız yıl
            return str(yil)
        k = next((x for x in kapanislar if x.yil == yil), None)
        return k.basligi() if k is not None else str(yil)

    data = [[""] + [_bas(yil) for yil in yillar] + [degisim_basligi(yillar)]]
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
            data.append([satir.etiket, *satir.hucreler, satir.degisim])
            renk = GRAY if satir.iyi is None else (_POZ if satir.iyi else _NEG)
            cmds += [("TEXTCOLOR", (-1, r), (-1, r), renk),
                     ("FONTNAME", (-1, r), (-1, r), FONT_B)]
            # Negatif hücreler kırmızı — ekranla aynı okuma.
            for i, negatif in enumerate(satir.eksi):
                if negatif:
                    cmds.append(("TEXTCOLOR", (i + 1, r), (i + 1, r), _NEG))
            r += 1

    genislik, yil_en = _genislikler(en, len(yillar))
    # repeatRows=1: tablo sayfaya sığmazsa yıl başlıkları her sayfada tekrar eder —
    # ekrandaki sabit başlığın PDF karşılığı.
    t = Table(data, colWidths=genislik, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), yazi_boyu(yil_en)),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), _PADDING),
        ("RIGHTPADDING", (0, 0), (-1, -1), _PADDING),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 1), (-2, -1), DARK),
    ] + cmds))
    return t


def mukayese_notu(kapanislar: list[YilKapanis] | None = None) -> Paragraph:
    """Tablo altı açıklama — ekrandaki dipnotun birebir aynısı."""
    stil = ParagraphStyle("mk_not", fontName=FONT, fontSize=7.4, textColor=GRAY, leading=10)
    # «Tutarlar TL'dir» YANLIŞTI: TL bölümü tablodan kaldırılınca not orada unutulmuştu.
    # Tablo dolar; birim «DOLAR BAZINDA (USD)» başlığında yazıyor, notta tekrarlanmıyor.
    yillar, _ = yillar_tablosu(kapanislar or [])
    parcalar = ["«—» hesaplanamadı", "hiç değişmeyen satırlar gizlendi"]
    if len(yillar) > 2:
        parcalar.append(f"son sütun: {yillar[0]}–{yillar[-2]} ortalamasına göre")
    parcalar.append("kaynak: stok hareketleri, cari, GL nakit")
    return Paragraph(" &#160;·&#160; ".join(parcalar), stil)
