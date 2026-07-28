"""
Yıllar arası mukayese tablosu — paylaşılan görünüm.

Trend & Oranlar sekmesi bunu doğrudan gösterir; Yapay Zekâ Yorumu ise aynı veriyi
modele gönderir. Tablo API anahtarı gerektirmez — kullanıcı yorum almadan da yıllar
arası gidişatı görebilmeli.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from domain.ai_yorum import YilKapanis, yillar_tablosu
from domain.ortak import tr_buyuk
from ui.gercek_durum_view import _agac, _c, _ic, _tsatir
from ui.styles import BAD as NEG
from ui.styles import BORDER, MUTED, PANEL_BG
from ui.styles import OK as POZ

_DARK = "#1f2937"
_BASLIK_RENK = "#0f766e"

# Sabit sütun genişlikleri: tablo pencereye yayılmaz, blok olarak ortalanır.
# «41,2 milyon» en uzun hücre; 100px ona göre seçildi.
_ETIKET_SUTUN = 246
_YIL_SUTUN = 100
_DEGISIM_SUTUN = 124   # «+310,89 puan» sığmalı


_AY_ADI = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def _kismi_bit(kapanislar: list[YilKapanis]) -> str:
    """Yıllar tam okunmadıysa ortak bitiş günü («07-28»); tamsa boş."""
    kismi = [k for k in kapanislar if not k.tam and len(k.bit) == 10]
    return kismi[-1].bit[5:] if kismi else ""


def _pencere_eki(kapanislar: list[YilKapanis]) -> str:
    """Başlığa eklenen dönem eki — kısmi yılda «· 1 Ocak – 28 Temmuz»."""
    ag = _kismi_bit(kapanislar)
    if not ag:
        return ""
    return f" &nbsp;·&nbsp; 1 Ocak – {int(ag[3:5])} {_AY_ADI[int(ag[:2]) - 1]}"


def _pencere_notu(kapanislar: list[YilKapanis]) -> str:
    ag = _kismi_bit(kapanislar)
    gun = f"{int(ag[3:5])} {_AY_ADI[int(ag[:2]) - 1]}"
    return (f"Yıl sürüyor: her yıl 1 Ocak – {gun} penceresinden okundu. Geçmiş yılı "
            "tam okuyup bu yılı yarım okumak kıyası bozardı.")


def _kapanis_notu(kapanislar: list[YilKapanis]) -> list[tuple[str, str]]:
    """Maliyet kapanışı yapılmamış yıl varsa kâr hücrelerinin neden boş olduğunu söyle."""
    eksik = [str(k.yil) for k in kapanislar if k.maliyet_eksik]
    if not eksik:
        return []
    return [(f"<b>{', '.join(eksik)}</b> için satışların maliyeti (62) henüz işlenmemiş. "
             "Kâr ve marj satırları o yıl «—» kalır: kapanış öncesi rakam gerçekte "
             "olduğundan yüksek çıkar, kıyaslamak yanıltır.", "")]


def mukayese_karti(kapanislar: list[YilKapanis]) -> QFrame | None:
    """
    Yıllar arası mukayese — DETERMİNİSTİK, modelden bağımsız.

    Model hangi satırı anacağını kendi seçiyordu; kullanıcı her seferinde tam mukayese
    istiyor. Bu tablo hep aynı satırları, hep tam gösterir. Model üstündeki metinde
    bunu yorumlar; üretmez.

    Tablo pencere genişliğine YAYILMAZ: en çok 5 yıl olduğu için sütunlar sabit
    genişlikte tutulup blok ortalanır. Yayılınca hücreler arası boşluk açılıyor ve
    satırı yatay takip etmek zorlaşıyordu.
    """
    yillar, bolumler = yillar_tablosu(kapanislar)
    if not yillar:
        return None

    kolon = 1 + len(yillar) + 1
    sabit = [(0, _ETIKET_SUTUN)]
    sabit += [(i + 1, _YIL_SUTUN) for i in range(len(yillar))]
    sabit.append((kolon - 1, _DEGISIM_SUTUN))
    t = _agac(kolon, sabit, esnek=0, hucre_renkli=True)
    t.header().setStretchLastSection(False)

    _tsatir(t, [_c("", renk=MUTED)]
            + [_c(str(yil), renk=MUTED, kalin=True, sag=True) for yil in yillar]
            + [_c(f"{yillar[0]}→{yillar[-1]}", renk=MUTED, kalin=True, sag=True)])

    for bolum in bolumler:
        if bolum.baslik:
            _tsatir(t, [_c(tr_buyuk(bolum.baslik), renk=_BASLIK_RENK, kalin=True)]
                    + [_c("")] * (kolon - 1))
        for satir in bolum.satirlar:
            renk = MUTED if satir.iyi is None else (POZ if satir.iyi else NEG)
            hucreler = [_c(satir.etiket)]
            for i, metin in enumerate(satir.hucreler):
                eksi = i < len(satir.eksi) and satir.eksi[i]
                hucreler.append(_c(metin, renk=NEG if eksi else _DARK, sag=True))
            hucreler.append(_c(satir.degisim, renk=renk, kalin=True, sag=True))
            _tsatir(t, hucreler)

    genislik = _ETIKET_SUTUN + _YIL_SUTUN * len(yillar) + _DEGISIM_SUTUN + 4
    t.setFixedWidth(genislik)
    t.setFixedHeight(30 * t.topLevelItemCount() + 6)

    notlar = [(_pencere_notu(kapanislar), "")] if _pencere_eki(kapanislar) else []
    notlar += _kapanis_notu(kapanislar)
    notlar += [("Yıllar boyunca hiç değişmeyen kalemler tabloda GÖSTERİLMEZ — "
               "karşılaştırma değeri taşımazlar.", ""),
              ("Alacak, borç ve nakit ilgili sekmelerin canlı kaynağından gelir "
               "(cari hareketler / GL nakit hesapları); stok, özkaynak ve aktif mizandan.", ""),
              ("Tutarlar TL'dir; büyük rakamlar «bin / milyon / milyar» diye kısaltılmıştır. "
               "Dolar karşılıkları Mikro'nun kendi kur kaydından hesaplanır.", ""),
              ("«—» o yıl için hesaplanamadı: payda sıfır, maliyet girilmemiş ya da "
               "özkaynak negatif.", "")]

    card = QFrame()
    card.setObjectName("aiCard")
    card.setStyleSheet(
        f"QFrame#aiCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; "
        "border-left: 3px solid #0f766e; border-radius: 12px; }")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 13, 16, 15)
    lay.setSpacing(8)
    lbl = QLabel(f"YILLAR ARASI MUKAYESE &nbsp;·&nbsp; {yillar[0]}–{yillar[-1]}"
                 + _pencere_eki(kapanislar))
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(
        "color: #0f766e; font-size: 13px; font-weight: 800; letter-spacing: 0.3px; "
        "background: transparent; border: none;")
    lay.addWidget(lbl)

    orta = QHBoxLayout()
    orta.addStretch(1)
    orta.addWidget(_ic(t, notlar))
    orta.addStretch(1)
    lay.addLayout(orta)
    return card
