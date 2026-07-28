"""
Yıllar arası mukayese tablosu — paylaşılan görünüm.

Mukayese & Oranlar sekmesi bunu doğrudan gösterir; Yapay Zekâ Yorumu ise aynı veriyi
modele gönderir. Tablo API anahtarı gerektirmez — kullanıcı yorum almadan da yıllar
arası gidişatı görebilmeli.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from domain.ai_yorum import YilKapanis, degisim_basligi, ortak_pencere, yillar_tablosu
from domain.ortak import tr_buyuk
from ui.gercek_durum_view import _agac, _c, _ic, _tsatir
from ui.styles import BAD as NEG
from ui.styles import BORDER, MUTED, PANEL_BG
from ui.styles import OK as POZ

_DARK = "#1f2937"
_BASLIK_RENK = "#0f766e"

# Sabit sütun genişlikleri: tablo pencereye yayılmaz, blok olarak ortalanır.
# «2025 (28.07–31.12)» en uzun hücre; sütun genişliği ona göre.
_ETIKET_SUTUN = 246
_YIL_SUTUN = 132   # «2025 (28.07–31.12)» sığmalı
_YIL_SUTUN_DAR = 96   # ortak pencerede başlık yalnız yıl; 10 sütun sığsın
_DEGISIM_SUTUN = 158   # «2026 / önceki ort.» ve «+310,89 puan» sığmalı

# Yıl başlıkları GERÇEK header'a konur, normal satıra değil: tablo uzun (40+ satır) ve
# aşağı inerken hangi sütunun hangi yıl olduğu görünmez oluyordu. Header sabit kalması
# için tablonun KENDİSİ kaymalı — bu yüzden yükseklik ekrana göre sınırlanır ve taşan
# kısım tablo içinde kaydırılır. Sınır ekrandan hesaplanır: sabit bir piksel değeri
# dizüstünde tabloyu bir avuç satıra düşürür, büyük ekranda boş yere kaydırma yaptırır.
_AZAMI_TABLO_YUKSEK = 560     # ekran okunamazsa (başsız test) makul varsayılan
_KAYDIRMA_GENISLIK = 14       # dikey kaydırma çubuğu ölçülemezse

_BASLIK_QSS = """
QHeaderView::section {
    background: #f1f5f9;
    color: #475569;
    padding: 7px 6px;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #cbd5e1;
    font-weight: 800;
    font-size: 11px;
}
"""


def _azami_yukseklik() -> int:
    """Tablonun ekranda kaplayabileceği en fazla yükseklik."""
    ekran = QApplication.primaryScreen()
    if ekran is None:
        return _AZAMI_TABLO_YUKSEK
    return max(360, min(900, int(ekran.availableGeometry().height() * 0.62)))


_AY_ADI = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def _kismi_var(kapanislar: list[YilKapanis]) -> bool:
    """Sütunlardan biri yılın tamamını kapsamıyorsa pencereler başlıkta yazılır."""
    return any(not k.tam for k in kapanislar)


def _pencere_eki(kapanislar: list[YilKapanis]) -> str:
    """
    Başlığa eklenen dönem eki — seçili aralığın kendisi.

    Eskiden «1 Ocak – 28 Temmuz» yazıyordu; üstteki tarih seçici 28.07.2025 derken
    başlıkta 1 Ocak görmek çelişkiydi ve zaten rapor gerçekten de aralık dışını
    okuyordu. Artık başlık seçilen aralığı, sütun başlıkları da her yılın o aralıktan
    aldığı parçayı gösterir.
    """
    if not _kismi_var(kapanislar):
        return ""
    ilk = min((k.bas for k in kapanislar if len(k.bas) == 10), default="")
    son = max((k.bit for k in kapanislar if len(k.bit) == 10), default="")
    if not ilk or not son:
        return ""
    ortak = ortak_pencere(kapanislar)
    if ortak:                       # hepsi aynı pencere → tek kez, kartın başlığında
        return f" &nbsp;·&nbsp; her yıl {ortak}"
    return (f" &nbsp;·&nbsp; {ilk[8:10]} {_AY_ADI[int(ilk[5:7]) - 1]} {ilk[:4]}"
            f" – {son[8:10]} {_AY_ADI[int(son[5:7]) - 1]} {son[:4]}")


def _sutun_basligi(kapanislar: list[YilKapanis], yil: int, ortak: str) -> str:
    """Pencere bütün sütunlarda aynıysa yalnız yıl; değilse sütunun kendi tarihi."""
    if ortak:
        return str(yil)
    k = next((x for x in kapanislar if x.yil == yil), None)
    return k.basligi() if k is not None else str(yil)


def _pencere_notu(kapanislar: list[YilKapanis]) -> str:
    if ortak_pencere(kapanislar):
        return ("Sütunların hepsi AYNI uzunlukta — satış ve kâr doğrudan mukayese "
                "edilebilir.")
    return ("Her sütun, seçtiğiniz aralığın o yıla düşen parçasıdır — başlıktaki gün "
            "aralığı budur. Sütunlar farklı uzunlukta olabilir: akış kalemlerini "
            "aylığa indirmeden mukayese etmeyin.")


def _degisim_notu(yillar: list[int]) -> str:
    """
    Son sütunun tabanı — dipnot satırına giren TEK parça.

    Ayrı bir paragraf yazılmıyor: sütun başlığı zaten «2026 / önceki ort.» diyor,
    burada yalnız hangi yılların ortalandığı açılıyor.
    """
    if len(yillar) < 3:
        return ""
    return f"son sütun: {yillar[0]}–{yillar[-2]} ortalamasına göre"


def _kapanis_notu(kapanislar: list[YilKapanis]) -> list[tuple[str, str]]:
    """Maliyet kapanışı yapılmamış yıl varsa kâr hücrelerinin neden boş olduğunu söyle."""
    eksik = [str(k.yil) for k in kapanislar if k.maliyet_eksik]
    if not eksik:
        return []
    # «Kâr ve marj» demek artık eksik: eksik fişin 153 ayağı stoğu da şişiriyor.
    return [(f"<b>{', '.join(eksik)}</b> için satışların maliyeti (62) işlenmemiş: "
             "kâr da stok da aynı tutarda şişik, o hücreler boş.", "")]


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

    # Ortak pencerede başlık yalnız yıl → sütun dar olabilir; farklıysa tam tarih sığmalı.
    ortak = ortak_pencere(kapanislar)
    yil_sutun = _YIL_SUTUN_DAR if ortak else _YIL_SUTUN
    kolon = 1 + len(yillar) + 1
    sabit = [(0, _ETIKET_SUTUN)]
    sabit += [(i + 1, yil_sutun) for i in range(len(yillar))]
    sabit.append((kolon - 1, _DEGISIM_SUTUN))
    t = _agac(kolon, sabit, esnek=0, hucre_renkli=True)
    hdr = t.header()
    hdr.setStretchLastSection(False)

    # BAŞLIK SATIRI SABİT. Eskiden normal bir satırdı; tablo aşağı kaydıkça başlık ekrandan
    # çıkıyor ve rakamın hangi yıla ait olduğu görünmüyordu. Sütun başlığı gerçek pencereyi
    # yazar: «2025 (28.07–31.12)» — sütunlar farklı uzunlukta olabilir ve bunun görünmemesi
    # akış kalemlerinde yanlış okumaya yol açar.
    t.setHeaderHidden(False)
    t.setHeaderLabels(
        [""] + [_sutun_basligi(kapanislar, yil, ortak) for yil in yillar]
        + [degisim_basligi(yillar)])
    hdr.setSectionsClickable(False)
    hdr.setSortIndicatorShown(False)
    t.setStyleSheet(t.styleSheet() + _BASLIK_QSS)
    basl_item = t.headerItem()
    for i in range(1, kolon):
        basl_item.setTextAlignment(
            i, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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

    genislik = _ETIKET_SUTUN + yil_sutun * len(yillar) + _DEGISIM_SUTUN + 4
    tam_yukseklik = (30 * t.topLevelItemCount() + 6
                     + max(hdr.sizeHint().height(), 28))
    azami = _azami_yukseklik()
    if tam_yukseklik > azami:
        # Taşan tablo KENDİ İÇİNDE kayar; sayfa kaydırılırsa başlık ekrandan çıkardı.
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        t.setFixedHeight(azami)
        genislik += t.verticalScrollBar().sizeHint().width() or _KAYDIRMA_GENISLIK
    else:
        t.setFixedHeight(tam_yukseklik)
    t.setFixedWidth(genislik)

    # ÜÇ NOT, DAHA FAZLASI DEĞİL. Altı paragraf uyarı tabloyu okunmaz yapıyordu; üstelik
    # biri YANLIŞTI: «Tutarlar TL'dir» notu, TL bölümü tablodan kaldırıldığında orada
    # unutulmuştu. Tablo dolar; 434.366'yı TL sanmak 47 kat yanlış okumaktır. Birim
    # zaten «DOLAR BAZINDA (USD)» başlığında yazıyor, notta tekrarına gerek yok.
    notlar = [(_pencere_notu(kapanislar), "")] if _pencere_eki(kapanislar) else []
    notlar += _kapanis_notu(kapanislar)
    # Not etiketleri DÜZ METİN (_ic düz QLabel kurar): «&nbsp;» harfi harfine basılır.
    dipnot = ["«—» hesaplanamadı", "hiç değişmeyen satırlar gizlendi"]
    if _degisim_notu(yillar):
        dipnot.append(_degisim_notu(yillar))
    dipnot.append("kaynak: stok hareketleri, cari, GL nakit")
    notlar += [("  ·  ".join(dipnot), "")]

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
