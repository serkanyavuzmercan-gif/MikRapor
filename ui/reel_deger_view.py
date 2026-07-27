"""Reel Değer & Finansman — karar destek görünümü."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from domain.mizan_bilanco import tl
from domain.reel_deger import DegerOzet, ReelDegerAnalizi
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height, _kpi_card
from ui.gercek_durum_view import NEG, POZ, _agac, _c, _card, _ic, _tsatir
from ui.styles import PRIMARY_SOFT


def _gun(v: float) -> str:
    return "—" if v < 0.05 else f"{v:.0f} gün"


def _deger_panel(baslik: str, o: DegerOzet, *, alacak: bool) -> QFrame:
    t = _agac(2, [(1, 145)])
    _tsatir(t, [_c("Nominal tutar"), _c(tl(o.nominal), kalin=True, sag=True)])
    _tsatir(t, [_c("Bugünkü ekonomik değer"), _c(tl(o.bugunku_deger), renk=ACCENT, kalin=True, sag=True)])
    etiket = "Vade maliyeti" if alacak else "Vade avantajı"
    renk = NEG if alacak else POZ
    _tsatir(t, [_c(etiket, kalin=True), _c(tl(o.vade_etkisi), renk=renk, kalin=True, sag=True)])
    _tsatir(t, [_c("Ağırlıklı vade"), _c(_gun(o.agirlikli_gun), sag=True)])
    _fit_height(t)
    aciklama = (
        "Tahsilat bekledikçe, aynı nominal alacağın bugünkü ekonomik değeri azalır."
        if alacak else
        "Ödeme vadesi uzadıkça, aynı nominal borcun bugünkü ekonomik yükü azalır."
    )
    return _card(baslik, _ic(t, [(aciklama, FAINT)]))


def _kart_panel(a: ReelDegerAnalizi) -> QFrame:
    k = a.kart
    t = _agac(5, [(0, 52), (1, 140), (2, 140), (3, 150), (4, 145)])
    _tsatir(t, [
        _c("Ay", renk=MUTED, kalin=True), _c("Açılış borcu", renk=MUTED, kalin=True, sag=True),
        _c("Ödeme", renk=MUTED, kalin=True, sag=True),
        _c("Finansman maliyeti", renk=MUTED, kalin=True, sag=True),
        _c("Kapanış borcu", renk=MUTED, kalin=True, sag=True),
    ])
    if not k.aylar:
        _tsatir(t, [_c("—"), _c("—"), _c("—"), _c("—"), _c("—")])
    for ay in k.aylar:
        _tsatir(t, [
            _c(str(ay.sira), kalin=True), _c(tl(ay.acilis_borc), sag=True),
            _c(tl(ay.odeme), renk=NEG if ay.odeme > 0.005 else FAINT, sag=True),
            _c(tl(ay.finansman_maliyeti) if ay.finansman_maliyeti > 0.005 else "—",
               renk="#b45309" if ay.finansman_maliyeti > 0.005 else FAINT, sag=True),
            _c(tl(ay.kapanis_borc), kalin=True, sag=True),
        ])
    _fit_height(t)

    if k.baslangic_borc < 0.005:
        notlar = [("Açık kredi kartı borcu bulunamadı.", FAINT)]
    elif k.kapandi_mi:
        if k.toplam_finansman_maliyeti < 0.005:
            notlar = [("Borç tam ödendiği için bu senaryoda kart finansman maliyeti oluşmuyor.", POZ)]
        else:
            notlar = [(
                f"Toplam finansman maliyeti: {tl(k.toplam_finansman_maliyeti)} · "
                f"toplam ödeme: {tl(k.toplam_odeme)}.", "#b45309")]
    else:
        notlar = [(
            f"{len(k.aylar)} ay sonunda kalan borç: {tl(k.kalan_borc)}. Bu senaryoda borç kapanmıyor.", NEG)]
    notlar.append((
        "Faiz, her ay ödenmeyen bakiye üzerinden hesaplanır. Vergi, gecikme cezası ve yeni kart harcaması "
        "bu ilk sürümde dahil değildir.", FAINT))
    return _card("KREDİ KARTI FİNANSMAN SENARYOSU", _ic(t, notlar))


def _bilgilendirme() -> QFrame:
    f = QFrame()
    f.setObjectName("reelDegerBilgi")
    f.setStyleSheet(
        "QFrame#reelDegerBilgi { background: #eef6ff; border: 1px solid #b8d6f2; border-radius: 10px; }"
    )
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(3)
    baslik = QLabel("BU RAPOR NEYİ GÖSTERİR?")
    baslik.setStyleSheet("color:#1d4f91; font-size:11px; font-weight:800; background:transparent;")
    lay.addWidget(baslik)
    metin = QLabel(
        "Nominal muhasebe tutarları değişmez. Bu analiz, vadeli alacak/borçların seçilen iskonto oranıyla "
        "bugünkü ekonomik değerini ve kart borcunun kısmi ödenmesi halinde oluşabilecek finansman maliyetini gösterir."
    )
    metin.setWordWrap(True)
    metin.setStyleSheet("color:#365676; font-size:12px; background:transparent;")
    lay.addWidget(metin)
    return f


def build_reel_deger_widget(a: ReelDegerAnalizi, *, bas: str, bit: str, firma: str = "") -> QWidget:
    content = QWidget()
    content.setObjectName("reelDegerContent")
    content.setStyleSheet("QWidget#reelDegerContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    v = a.varsayim
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>REEL DEĞER &amp; FİNANSMAN &nbsp;·&nbsp; "
        f"{bit} itibarıyla{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Yıllık iskonto / fırsat maliyeti: "
        f"%{v.yillik_iskonto_yuzde:.1f} · kart aylık finansman maliyeti: "
        f"%{v.kart_aylik_faiz_yuzde:.1f} · kart ödeme oranı: %{v.kart_odeme_yuzde:.0f}.</span>"
    )
    head.setTextFormat(Qt.TextFormat.RichText)
    head.setStyleSheet("background: transparent;")
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, bit, kaynak="canli"))
    root.addWidget(_bilgilendirme())

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("NOMİNAL ALACAK", tl(a.alacak.nominal), PRIMARY_SOFT, ACCENT))
    kpi.addWidget(_kpi_card("ALACAĞIN BUGÜNKÜ DEĞERİ", tl(a.alacak.bugunku_deger), "#eef6ff", "#1d4f91"))
    kpi.addWidget(_kpi_card("NOMİNAL BORÇ", tl(a.borc.nominal), "#fdf3e0", "#b45309"))
    kpi.addWidget(_kpi_card("BORCUN BUGÜNKÜ DEĞERİ", tl(a.borc.bugunku_deger), "#fff7ed", "#b45309"))
    net_bg, net_renk = ("#e8f6ee", POZ) if a.reel_net_pozisyon >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("REEL NET POZİSYON", tl(a.reel_net_pozisyon), net_bg, net_renk))
    root.addLayout(kpi)

    fark = a.net_vade_etkisi
    if abs(fark) > 0.005:
        renk = NEG if fark < 0 else POZ
        yon = "azaltıyor" if fark < 0 else "artırıyor"
        etki = QLabel(
            f"<b>Vade etkisi:</b> Alacak ve borçların vade yapısı, net ekonomik pozisyonu "
            f"{tl(abs(fark))} {yon}."
        )
        etki.setTextFormat(Qt.TextFormat.RichText)
        etki.setStyleSheet(
            f"QLabel {{ background: {'#fdecec' if fark < 0 else '#e8f6ee'}; "
            f"border: 1px solid {'#f0b4b4' if fark < 0 else '#bfe3cd'}; border-radius: 8px; "
            f"color: {renk}; padding: 10px 13px; font-size: 12px; }}"
        )
        root.addWidget(etki)

    row = QHBoxLayout()
    row.setSpacing(20)
    row.addWidget(_deger_panel("ALACAKLARIN REEL DEĞERİ", a.alacak, alacak=True), 1)
    row.addWidget(_deger_panel("BORÇLARIN REEL DEĞERİ", a.borc, alacak=False), 1)
    root.addLayout(row)
    root.addWidget(_kart_panel(a))
    root.addStretch(1)
    return content
