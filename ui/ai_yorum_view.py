"""
Yapay Zekâ Yorumu — yerel Qt görünümü.

Model çıktısı sade Markdown'dır (## başlık, - madde). Ağır bir Markdown motoru yerine
küçük bir dönüştürücü kullanılır: bağımlılık eklemez ve modelin ürettiği biçimi birebir
karşılar. Bölüm kartları diğer tablarla aynı dili konuşur (_card).
"""

from __future__ import annotations

import html
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.ai_yorum import AiYorum, yillar_tablosu
from domain.ortak import tr_buyuk, tr_kucuk
from ui.bilanco_view import FAINT, MUTED, PAGE_BG
from ui.gercek_durum_view import _agac, _c, _ic, _tsatir
from ui.styles import BAD as NEG
from ui.styles import BORDER, PANEL_BG
from ui.styles import OK as POZ

_DARK = "#1f2937"

# Sabit sütun genişlikleri: tablo pencereye yayılmaz, blok olarak ortalanır.
# «41,2 milyon» en uzun hücre; 100px ona göre seçildi.
_ETIKET_SUTUN = 246
_YIL_SUTUN = 100
_DEGISIM_SUTUN = 104

# Başlığa göre kenar rengi — "dikkat" kırmızı, "iyi giden" yeşil; göz taramayı hızlandırır.
_BOLUM_RENK = (
    ("dikkat", NEG),
    ("risk", NEG),
    ("karar", "#b45309"),
    ("iyi giden", POZ),
    ("özet", "#0f766e"),
)


def _bolum_rengi(baslik: str) -> str:
    dusuk = tr_kucuk(baslik)
    for anahtar, renk in _BOLUM_RENK:
        if anahtar in dusuk:
            return renk
    return MUTED


def _satir_ici(metin: str) -> str:
    """**kalın** ve `kod` işaretlerini HTML'e çevirir; gerisi kaçışlanır."""
    guvenli = html.escape(metin)
    guvenli = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", guvenli)
    guvenli = re.sub(r"`(.+?)`", r"<code>\1</code>", guvenli)
    return guvenli


def bolumlere_ayir(metin: str) -> list[tuple[str, list[str]]]:
    """
    Markdown metnini (başlık, satırlar) listesine böler.

    '## ' ile başlayan satır yeni bölüm açar. Başlıksız girişteki metin
    'Yorum' başlığı altında toplanır — model biçimi tutturamazsa da kaybolmasın.
    """
    bolumler: list[tuple[str, list[str]]] = []
    baslik = ""
    tampon: list[str] = []

    def _kapat() -> None:
        if tampon and any(s.strip() for s in tampon):
            bolumler.append((baslik or "Yorum", [s for s in tampon if s.strip()]))

    for ham in metin.splitlines():
        satir = ham.rstrip()
        if satir.startswith("#"):
            _kapat()
            baslik = satir.lstrip("#").strip()
            tampon = []
        else:
            tampon.append(satir)
    _kapat()
    return bolumler


def _bolum_karti(baslik: str, satirlar: list[str]) -> QFrame:
    renk = _bolum_rengi(baslik)
    card = QFrame()
    card.setObjectName("aiCard")
    card.setStyleSheet(
        f"QFrame#aiCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; "
        f"border-left: 3px solid {renk}; border-radius: 12px; }}"
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 13, 16, 15)
    lay.setSpacing(8)

    lbl = QLabel(html.escape(tr_buyuk(baslik)))
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(
        f"color: {renk}; font-size: 13px; font-weight: 800; letter-spacing: 0.3px; "
        "background: transparent; border: none;")
    lay.addWidget(lbl)

    for satir in satirlar:
        s = satir.strip()
        madde = s.startswith(("- ", "* ", "• "))
        if madde:
            s = s[2:].strip()
        else:
            s = re.sub(r"^\d+[.)]\s+", "", s)
        govde = QLabel(("•&nbsp;&nbsp;" if madde else "") + _satir_ici(s))
        govde.setTextFormat(Qt.TextFormat.RichText)
        govde.setWordWrap(True)
        govde.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        govde.setStyleSheet(
            f"color: {_DARK}; font-size: 13px; background: transparent; border: none; "
            + ("margin-left: 6px;" if madde else ""))
        lay.addWidget(govde)
    return card


def _mukayese_karti(y: AiYorum) -> QFrame | None:
    """
    Yıllar arası mukayese — DETERMİNİSTİK, modelden bağımsız.

    Model hangi satırı anacağını kendi seçiyordu; kullanıcı her seferinde tam mukayese
    istiyor. Bu tablo hep aynı satırları, hep tam gösterir. Model üstündeki metinde
    bunu yorumlar; üretmez.

    Tablo pencere genişliğine YAYILMAZ: en çok 5 yıl olduğu için sütunlar sabit
    genişlikte tutulup blok ortalanır. Yayılınca hücreler arası boşluk açılıyor ve
    satırı yatay takip etmek zorlaşıyordu.
    """
    yillar, bolumler = yillar_tablosu(y.kapanislar)
    if not yillar:
        return None

    kolon = 1 + len(yillar) + 1
    sabit = [(0, _ETIKET_SUTUN)]
    sabit += [(i + 1, _YIL_SUTUN) for i in range(len(yillar))]
    sabit.append((kolon - 1, _DEGISIM_SUTUN))
    t = _agac(kolon, sabit, esnek=0)
    t.header().setStretchLastSection(False)

    _tsatir(t, [_c("", renk=MUTED)]
            + [_c(str(yil), renk=MUTED, kalin=True, sag=True) for yil in yillar]
            + [_c(f"{yillar[0]}→{yillar[-1]}", renk=MUTED, kalin=True, sag=True)])

    sabit_var = False
    for bolum in bolumler:
        if bolum.baslik:
            _tsatir(t, [_c(tr_buyuk(bolum.baslik), renk="#0f766e", kalin=True)]
                    + [_c("")] * (kolon - 1))
        for satir in bolum.satirlar:
            sabit_var = sabit_var or satir.sabit
            renk = MUTED if satir.iyi is None else (POZ if satir.iyi else NEG)
            hucreler = [_c(satir.etiket + ("  ⚠" if satir.sabit else ""),
                           renk=MUTED if satir.sabit else _DARK)]
            for i, metin in enumerate(satir.hucreler):
                eksi = i < len(satir.eksi) and satir.eksi[i]
                hucreler.append(_c(metin, renk=NEG if eksi else _DARK, sag=True))
            hucreler.append(_c(satir.degisim, renk=renk, kalin=True, sag=True))
            _tsatir(t, hucreler)

    genislik = _ETIKET_SUTUN + _YIL_SUTUN * len(yillar) + _DEGISIM_SUTUN + 4
    t.setFixedWidth(genislik)
    t.setFixedHeight(30 * t.topLevelItemCount() + 6)

    notlar = [("Alacak, borç ve nakit ilgili sekmelerin canlı kaynağından gelir "
               "(cari hareketler / GL nakit hesapları); stok, özkaynak ve aktif mizandan.", ""),
              ("Tutarlar TL'dir; büyük rakamlar «bin / milyon / milyar» diye kısaltılmıştır. "
               "Dolar karşılıkları Mikro'nun kendi kur kaydından hesaplanır.", ""),
              ("«—» o yıl için hesaplanamadı: payda sıfır, maliyet girilmemiş ya da "
               "özkaynak negatif.", "")]
    if sabit_var:
        # Bilanço hesapları işlenmediğinde mizan her yıl aynı çıkar. Sessiz kalırsak
        # kullanıcı "trend yok" sanır; oysa sorun veride (canlıda birebir görüldü).
        notlar.insert(0, (
            "⚠ işaretli satırlar tüm yıllarda AYNI: bu kalemler muhasebede güncellenmemiş "
            "olabilir. Bu satırlara ve onlardan türeyen oranlara güvenmeyin.", "uyari"))

    card = QFrame()
    card.setObjectName("aiCard")
    card.setStyleSheet(
        f"QFrame#aiCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; "
        "border-left: 3px solid #0f766e; border-radius: 12px; }")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 13, 16, 15)
    lay.setSpacing(8)
    lbl = QLabel(f"YILLAR ARASI MUKAYESE &nbsp;·&nbsp; {yillar[0]}–{yillar[-1]}")
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


def build_ai_yorum_widget(y: AiYorum, firma: str = "") -> QWidget:
    """Bir AiYorum'dan görünüm üretir."""
    content = QWidget()
    content.setObjectName("aiContent")
    content.setStyleSheet("QWidget#aiContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(12)

    firma_str = f" &nbsp;·&nbsp; <b>{html.escape(firma or y.firma)}</b>" if (firma or y.firma) else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>YAPAY ZEKÂ YORUMU &nbsp;·&nbsp; "
        f"{html.escape(y.aralik)}{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Model: {html.escape(y.model)} &nbsp;·&nbsp; "
        f"Gönderilen: {html.escape(y.veri_ozeti)}</span>"
    )
    head.setTextFormat(Qt.TextFormat.RichText)
    head.setWordWrap(True)
    head.setStyleSheet("background: transparent;")
    root.addWidget(head)

    for baslik, satirlar in bolumlere_ayir(y.metin):
        root.addWidget(_bolum_karti(baslik, satirlar))

    # Mukayese tablosu EN ALTTA: önce okunacak yorum, sonra dayanağı olan rakamlar.
    mukayese = _mukayese_karti(y)
    if mukayese is not None:
        root.addWidget(mukayese)

    dipnot = QLabel(
        "Bu yorum yapay zekâ tarafından üretilmiştir; mali müşavir görüşü yerine geçmez. "
        "Karar vermeden önce rakamları ilgili sekmeden doğrulayın."
    )
    dipnot.setWordWrap(True)
    dipnot.setStyleSheet(f"color: {FAINT}; font-size: 11px; background: transparent;")
    root.addWidget(dipnot)
    root.addStretch(1)
    return content
