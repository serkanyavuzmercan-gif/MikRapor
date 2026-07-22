"""
Nakit Akış — yerel Qt görünümü.

Banka + kasa fiili hareketlerinden nakit akış tablosu: açılış → girişler → çıkışlar → kapanış,
kategori kırılımları (tahsilat, satıcı ödemesi, kredi, vergi…), kredi özeti ve yaklaşan taksitler.
Kart/satır yardımcıları diğer sekmelerle paylaşılır. (Aylık trend: Trend & Oranlar sekmesinde.)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from domain.kredi import KrediOzet
from domain.mizan_bilanco import tl
from domain.nakit_akis import NakitAkis
from domain.runway import runway_nakit_akistan
from ui.bilanco_view import ACCENT, FAINT, MUTED, PAGE_BG, _fit_height, _kpi_card
from ui.gercek_durum_view import (
    NEG,
    POZ,
    _agac,
    _c,
    _card,
    _ic,
    _renk,
    _tsatir,
)
from ui.styles import PRIMARY_SOFT, SUBINK
from ui.tahsilat_alacak_view import _oran_bar


def _ozet_panel(na: NakitAkis) -> QFrame:
    t = _agac(2, [(1, 140)])
    _tsatir(t, [_c("Açılış Nakit", kalin=True), _c(tl(na.acilis_nakit), kalin=True, sag=True)])
    _tsatir(t, [_c("Toplam Giriş (+)"), _c(tl(na.toplam_giris), renk=POZ, sag=True)])
    _tsatir(t, [_c("Toplam Çıkış (−)"), _c(tl(-na.toplam_cikis), renk=NEG, sag=True)])
    _tsatir(t, [_c("Net Nakit Akışı", kalin=True),
                _c(tl(na.net_akis), renk=_renk(na.net_akis), kalin=True, sag=True)])
    _tsatir(t, [_c("Kapanış Nakit", kalin=True),
                _c(tl(na.kapanis_nakit), renk=_renk(na.kapanis_nakit), kalin=True, sag=True)])
    _fit_height(t)

    notlar: list[tuple[str, str]] = []
    if abs(na.mutabakat_farki) > max(1000.0, na.kapanis_nakit * 0.01):
        kredi_net = na.kredi_net_gosterim
        kredi_ek = (
            f" Bunun net ~{tl(kredi_net)}'si dönemde çekilen kredidir (bkz. KREDİ ÖZETİ);"
            if kredi_net > 0.005 else ""
        )
        notlar.append((
            f"Mutabakat: açılış + net akış = {tl(na.kapanis_hesaplanan)}; gerçek banka "
            f"kapanışıyla {tl(na.mutabakat_farki)} fark.{kredi_ek} kalanı sınıflandırılamayan "
            "hareket (kur farkı / iç transfer / karşı tarafı eşleşmeyen tahsilat-ödeme) — "
            "akış eksik olabilir.", "#b45309"))
    return _card("NAKİT AKIŞ ÖZETİ", _ic(t, notlar))


def _kategori_panel(baslik: str, kategori: dict, toplam: float, renk: str,
                    diger_kirilim: list | None = None, diger_etiket: str = "Diğer") -> QFrame:
    t = _agac(3, [(0, 160), (2, 130)], esnek=1)
    if not kategori:
        _tsatir(t, [_c("Hareket yok.", renk=FAINT), _c(""), _c("")])
        _fit_height(t)
        return _card(baslik, _ic(t))

    enb = max(kategori.values(), default=0.0) or 1.0
    for ad, tutar in kategori.items():
        it = _tsatir(t, [_c(ad), _c(""), _c(tl(tutar), renk=renk, kalin=True, sag=True)])
        t.setItemWidget(it, 1, _oran_bar(tutar / enb, renk))
        # "Diğer" satırının altına karşı-taraf kodu kırılımını döker (saklı kalmasın)
        if ad == diger_etiket and diger_kirilim:
            for prefix, kt in diger_kirilim:
                _tsatir(t, [_c(f"      ◦ {prefix or '?'} hesabı", renk=FAINT), _c(""),
                            _c(tl(kt), renk=FAINT, sag=True)])
    _tsatir(t, [_c("Toplam", kalin=True), _c(""), _c(tl(toplam), kalin=True, sag=True)])
    _fit_height(t)
    return _card(baslik, _ic(t))


def _kredi_panel(na: NakitAkis) -> QFrame:
    net = na.kredi_net_gosterim
    t = _agac(2, [(1, 140)])
    _tsatir(t, [_c("Kredi Kullanımı (brüt)"), _c(tl(na.kredi_kullanim_gosterim), renk=POZ, sag=True)])
    _tsatir(t, [_c("Kredi Ödemesi (brüt)"), _c(tl(-na.kredi_odeme_gosterim), renk=NEG, sag=True)])
    _tsatir(t, [_c("Net Kredi (gerçek değişim)", kalin=True),
                _c(tl(net), renk=_renk(net), kalin=True, sag=True)])
    _fit_height(t)

    aciklama = (
        "Dönemde net borçlanma (borç arttı)." if net > 0.005 else
        "Dönemde net kredi geri ödemesi (borç azaldı)." if net < -0.005 else
        "Dönemde kredi hareketi dengede / yok."
    )
    notlar: list[tuple[str, str]] = [(aciklama, FAINT)]
    notlar.append((
        "Kullanım/ödeme BRÜTtür: rotatif kredi yenilemeleri, faiz ve kur farkı bu iki satırı "
        "şişirir (aynı limit birçok kez dönebilir). Dönemin gerçek borç değişimi «Net Kredi»dir.",
        FAINT))
    if na.kredi_kaynak_gl:
        notlar.append((
            "Kaynak: muhasebe (300/303); üstteki Toplam Çıkış'a dâhil değildir.", FAINT))
    return _card("KREDİ ÖZETİ", _ic(t, notlar))


_AY_KISA = ("Oca", "Şub", "Mar", "Nis", "May", "Haz",
            "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")


def _ay_str(yyyymm: str) -> str:
    """'2026-12' → 'Ara 2026'."""
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
        return f"{_AY_KISA[m - 1]} {y}"
    except (ValueError, IndexError):
        return yyyymm


def _runway_banner(na: NakitAkis) -> QWidget | None:
    """Nakit runway özeti: 'paran kaç ay yeter / hangi ay eksiye düşer'."""
    if na.hareket_sayisi == 0:
        return None
    r = runway_nakit_akistan(na, ufuk_ay=12)
    hiz = ("+" if r.aylik_net_ort >= 0 else "−") + tl(abs(r.aylik_net_ort))
    alt = (
        f"Aylık ortalama net nakit {hiz}  ·  mevcut nakit {tl(r.baslangic_nakit)}"
    )

    # ── Güvenilirlik: net akış gerçeği yansıtmıyorsa iyimser yorumu BASTIR ──
    # (a) Banka bakiye değişiminin büyük kısmı kategorize edilemediyse akış eksiktir.
    # (b) Nakit artışı operasyondan değil, dönemde çekilen krediden geliyorsa "güç" sahtedir.
    brut = na.toplam_giris + na.toplam_cikis
    kredi_net = na.kredi_net_gosterim  # gerçek net borçlanma (brüt kullanım/ödeme değil)
    guvenilmez = abs(na.mutabakat_farki) > max(50000.0, 0.30 * brut)
    kredi_bagimli = na.net_akis > -0.005 and kredi_net > max(0.005, na.net_akis)

    if guvenilmez or kredi_bagimli:
        renk, bg, kenar = "#b45309", "#fdf3e0", "#f0d090"
        baslik = "Nakit yorumu güvenilmez — artış sağlıklı görünse de aldatıcı olabilir"
        parcalar = []
        if kredi_net > 0.005:
            parcalar.append(f"dönemde net {tl(kredi_net)} borçlanma olmuş (kapanış nakit bundan şişkin)")
        if guvenilmez:
            parcalar.append(f"{tl(abs(na.mutabakat_farki))} hareket sınıflandırılamadı (net akış eksik)")
        oneri = "→ " + "; ".join(parcalar).capitalize() + ". Borçlanmayı ve eksik gideri çıkarınca gerçek nakit üretimi çok daha düşük."
    elif r.tukenme_ay is not None:
        renk, bg, kenar = NEG, "#fdecec", "#f3b4b4"
        gun = f"~{r.tukenme_gun} gün sonra " if r.tukenme_gun else ""
        baslik = f"Nakit {gun}({_ay_str(r.tukenme_ay)}) eksiye düşüyor"
        oneri = "→ Tahsilatı öne çek, öteleyebileceğin ödemeleri ertele."
    elif r.eriyor:
        renk, bg, kenar = "#b45309", "#fdf3e0", "#f0d090"
        baslik = f"Nakit eriyor — 12 ay ufkunda tükenmiyor ama trend aşağı ({hiz}/ay)"
        oneri = "→ Nakit hızını izle; giderleri gözden geçir."
    else:
        renk, bg, kenar = "#15803d", "#e8f6ee", "#bfe3cd"
        baslik = f"Nakit güçleniyor — mevcut hızla artıyor ({hiz}/ay)"
        oneri = ""

    card = QFrame()
    card.setObjectName("runwayBanner")
    card.setStyleSheet(
        f"QFrame#runwayBanner {{ background: {bg}; border: 1px solid {kenar}; "
        f"border-radius: 12px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 12, 18, 12)
    lay.setSpacing(2)
    eyebrow = QLabel("NAKİT NE KADAR YETER?")
    eyebrow.setStyleSheet(
        f"color: {renk}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; "
        "background: transparent;"
    )
    lay.addWidget(eyebrow)
    bl = QLabel(baslik)
    bl.setWordWrap(True)
    bl.setStyleSheet(
        f"color: {renk}; font-size: 18px; font-weight: 800; background: transparent;"
    )
    lay.addWidget(bl)
    sub = QLabel(alt + (f"   {oneri}" if oneri else ""))
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
    lay.addWidget(sub)
    return card


def _vade_goster(vade: str) -> str:
    """'2026-11-15' → '15.11.2026'."""
    try:
        y, m, d = vade[:4], vade[5:7], vade[8:10]
        return f"{d}.{m}.{y}"
    except (ValueError, IndexError):
        return vade


def _yaklasan_taksit_panel(oz: KrediOzet) -> QFrame:
    """Ödenmemiş kredi taksitleri — sıradaki vade/banka/tutar + toplam."""
    t = _agac(4, [(0, 145), (1, 105), (3, 120)], esnek=2)
    _tsatir(t, [_c("Vade", renk=MUTED, kalin=True), _c("Banka Kodu", renk=MUTED, kalin=True),
                _c("Banka", renk=MUTED, kalin=True), _c("Tutar", renk=MUTED, kalin=True, sag=True)])
    for tk in oz.taksitler:
        _tsatir(t, [_c(_vade_goster(tk.vade), kalin=True), _c(tk.banka or "—", renk=FAINT),
                    _c(tk.banka_ad or "—", renk=SUBINK), _c(tl(tk.tutar), renk=NEG, sag=True)])

    notlar: list[tuple[str, str]] = []
    if oz.adet < 1:
        _tsatir(t, [_c("Ödenmemiş kredi taksiti bulunamadı.", renk=FAINT), _c(""), _c(""), _c("")])
    else:
        _tsatir(t, [_c(f"Toplam ({oz.adet} taksit)", kalin=True), _c(""), _c(""),
                    _c(tl(oz.toplam), renk=NEG, kalin=True, sag=True)])
        if oz.toplam_faiz > 0.005:
            notlar.append((
                f"içinde faiz {tl(oz.toplam_faiz)} · anapara {tl(oz.toplam_anapara)}", FAINT))
        if oz.gecikmis_tutar > 0.005:
            notlar.append((
                f"⚠ {oz.gecikmis_adet} taksit ({tl(oz.gecikmis_tutar)}) vadesi geçmiş, "
                "hâlâ ödenmemiş görünüyor.", "#8a5a00"))
    _fit_height(t)
    return _card("YAKLAŞAN KREDİ TAKSİTLERİ", _ic(t, notlar))


def build_nakit_akis_widget(
    na: NakitAkis, firma: str = "", kredi: KrediOzet | None = None,
) -> QWidget:
    """Bir NakitAkis'ten QScrollArea içine konacak yerel görünüm üretir."""
    content = QWidget()
    content.setObjectName("naContent")
    content.setStyleSheet("QWidget#naContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>NAKİT AKIŞ &nbsp;·&nbsp; "
        f"{na.bas} → {na.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Banka ve kasadan fiilen geçen para — "
        f"karşı tarafına göre kategorize (tahsilat, satıcı ödemesi, kredi, vergi…). "
        f"Banka↔banka/kasa iç transferleri hariç.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, na.bit, kaynak="canli"))

    if na.hareket_sayisi == 0:
        uyari = QLabel(
            "⚠ <b>Bu dönemde banka/kasa hareketi bulunamadı.</b> Mikro'da veri olan dönemi seçin; "
            "«Mikro Ayarları»'ndaki çalışma yılı ile dönem tarihleri uyumlu olmalı."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdf3e0; border: 1px solid #f0d090; border-radius: 8px; "
            "color: #8a5a00; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card("TOPLAM GİRİŞ", tl(na.toplam_giris), "#e8f6ee", POZ))
    kpi.addWidget(_kpi_card("TOPLAM ÇIKIŞ", tl(na.toplam_cikis), "#fdecec", NEG))
    nk_bg, nk_vr = ("#e8f6ee", POZ) if na.net_akis >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("NET NAKİT AKIŞI", tl(na.net_akis), nk_bg, nk_vr))
    kp_bg, kp_vr = (PRIMARY_SOFT, ACCENT) if na.kapanis_nakit >= 0 else ("#fdecec", NEG)
    kpi.addWidget(_kpi_card("KAPANIŞ NAKİT", tl(na.kapanis_nakit), kp_bg, kp_vr))
    root.addLayout(kpi)

    # Nakit Runway — "paran kaç ay yeter / hangi ay eksiye düşer"
    banner = _runway_banner(na)
    if banner is not None:
        root.addWidget(banner)

    row1 = QHBoxLayout()
    row1.setSpacing(20)
    row1.addWidget(_kategori_panel("GİRİŞLER", na.giris_kategori, na.toplam_giris, POZ,
                                   na.diger_giris_kirilim, "Diğer girişler"), 1)
    row1.addWidget(_kategori_panel("ÇIKIŞLAR", na.cikis_kategori, na.toplam_cikis, NEG,
                                   na.diger_cikis_kirilim, "Diğer çıkışlar"), 1)
    root.addLayout(row1)

    row2 = QHBoxLayout()
    row2.setSpacing(20)
    row2.addWidget(_ozet_panel(na), 1)
    row2.addWidget(_kredi_panel(na), 1)
    root.addLayout(row2)

    if kredi is not None and kredi.adet > 0:
        root.addWidget(_yaklasan_taksit_panel(kredi))

    root.addStretch(1)
    return content
