"""
Gelir Tablosu — yerel Qt görünümü (tek sütun şelale + KPI kartları).

bilanco_view'ın ortak yardımcılarını (tree/satır/KPI/panel + hover + zebra) yeniden kullanır;
gelir tablosu tek sütunlu şelale olduğu için ayrı bir düzenleyici. Veri modeli GelirTablosu.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from domain.gelir_tablosu import GelirTablosu, yuzde
from domain.mizan_bilanco import tl
from ui.bilanco_view import (
    FAINT,
    MUTED,
    NAVY,
    PAGE_BG,
    _fit_height,
    _kpi_card,
    _panel,
    _row,
    _section,
    _tree,
)
from ui.styles import ACCENT, PRIMARY_SOFT

_SOLUK = "#94a3b8"  # maliyet kapanışı yokken şişik kâr satırları


def _doldur(t, gt: GelirTablosu) -> None:
    # Maliyet kapanışı yoksa kâr sonuçları (brüt/faaliyet/net) şişik → soluklaştır.
    # Net Satışlar gerçek olduğu için normal kalır.
    kapanis_yok = gt.maliyet_eksik
    for s in gt.satirlar:
        if s.tip == "bolum":
            _section(t, s.etiket)
        elif s.tip == "hesap":
            _row(t, f"   {s.etiket}", s.tutar or 0.0)
        else:  # sonuc — yürüyen ara/nihai sonuç (vurgulu)
            if s.etiket.startswith("DÖNEM NET"):
                if kapanis_yok:
                    renk = _SOLUK
                else:
                    renk = "#15803d" if (s.tutar or 0) >= 0 else "#b91c1c"
                _row(t, s.etiket, s.tutar or 0.0, big=True, renk=renk)
            elif kapanis_yok and not s.etiket.startswith("NET SATIŞLAR"):
                _row(t, s.etiket, s.tutar or 0.0, bold=True, renk=_SOLUK)
            else:
                _row(t, s.etiket, s.tutar or 0.0, bold=True, renk=NAVY)
    _fit_height(t)


_KPI_SOLUK_BG = "#eef1f5"
_KPI_SOLUK_VR = "#94a3b8"


def build_gelir_tablosu_widget(gt: GelirTablosu, firma: str = "") -> QWidget:
    """Bir GelirTablosu'ndan, QScrollArea içine konacak yerel görünüm üretir."""
    nk_bg, nk_vr = ("#e8f6ee", "#15803d") if gt.net_kar >= 0 else ("#fdecec", "#b91c1c")

    content = QWidget()
    content.setObjectName("gtContent")
    content.setStyleSheet("QWidget#gtContent { background: %s; }" % PAGE_BG)
    root = QVBoxLayout(content)
    root.setContentsMargins(16, 14, 16, 16)
    root.setSpacing(14)

    firma_str = f" &nbsp;·&nbsp; <b>{firma}</b>" if firma else ""
    head = QLabel(
        f"<span style='color:{MUTED}; font-size:11px;'>GELİR TABLOSU &nbsp;·&nbsp; "
        f"{gt.bas} → {gt.bit} dönemi{firma_str}</span><br>"
        f"<span style='color:{NAVY}; font-size:12px;'>Bu dönemde şirket <b>kazandı mı, "
        f"kaybetti mi?</b> Satıştan başlar; maliyet ve giderler düşülür. En alttaki "
        f"«<b>Dönem Net Kârı</b>» cebe kalan tutardır.</span><br>"
        f"<span style='color:{FAINT}; font-size:11px;'>Dönem Net Kârı, bilançodaki "
        f"«Dönem Net Kârı» ile birebir tutar (aynı 6xx hesaplarından) — yerleşik mutabakat.</span>"
    )
    head.setStyleSheet("background: transparent;")
    head.setTextFormat(Qt.TextFormat.RichText)
    from ui.bilesenler import baslik_ile_gelecek_uyari
    root.addWidget(baslik_ile_gelecek_uyari(head, gt.bit, kaynak="resmi"))

    if gt.maliyet_eksik:
        uyari = QLabel(
            "⚠ <b>Satışların Maliyeti (62) bu dönemde neredeyse sıfır.</b> Mal satan bir "
            "işletmeyseniz <b>maliyet kapanışı henüz yapılmamış</b> demektir; brüt/net kâr "
            "GERÇEKTE OLDUĞUNDAN ÇOK YÜKSEK görünür. Maliyet kapanışı yapılmış (kapatılmış) "
            "bir dönem seçin ya da Mikro'da maliyet kapanışından sonra bakın."
        )
        uyari.setWordWrap(True)
        uyari.setTextFormat(Qt.TextFormat.RichText)
        uyari.setStyleSheet(
            "QLabel { background: #fdecec; border: 1px solid #f3c0c0; border-radius: 8px; "
            "color: #8a1c1c; padding: 11px 14px; font-size: 12px; }"
        )
        root.addWidget(uyari)

    ke = gt.maliyet_eksik

    def _kar_kpi(baslik: str, tutar: float, marj: float, *, son: bool = False):
        # Kapanış yoksa: şişik kâr → gri + "kapanış öncesi", sahte % gösterme.
        if ke:
            dipnot = "kapanış öncesi · güvenilmez" if son else "kapanış öncesi"
            return _kpi_card(baslik, "≈ " + tl(tutar), _KPI_SOLUK_BG, _KPI_SOLUK_VR, alt=dipnot)
        bg, vr = (nk_bg, nk_vr) if son else (PRIMARY_SOFT, ACCENT)
        return _kpi_card(f"{baslik}  ·  {yuzde(marj)}", tl(tutar), bg, vr)

    kpi = QHBoxLayout()
    kpi.setSpacing(12)
    kpi.addWidget(_kpi_card(
        "NET SATIŞLAR", tl(gt.net_satislar), PRIMARY_SOFT, ACCENT,
        alt="gerçekleşen ciro" if ke else "",
    ))
    kpi.addWidget(_kar_kpi("BRÜT KÂR", gt.brut_kar, gt.brut_marj))
    kpi.addWidget(_kar_kpi("FAALİYET KÂRI", gt.faaliyet_kari, gt.faaliyet_marj))
    kpi.addWidget(_kar_kpi("DÖNEM NET KÂRI", gt.net_kar, gt.net_marj, son=True))
    root.addLayout(kpi)

    t = _tree()
    t.setColumnWidth(1, 160)
    _doldur(t, gt)
    panel = _panel("GELİR TABLOSU (Kâr/Zarar)", t)
    # Tek sütun şelale tüm ekrana yayılınca etiket–tutar arası dev boşluk oluşuyor;
    # tabloyu okunur bir "belge genişliğine" (~700px) sabitleyip sola yaslıyoruz.
    # min+max birlikte: sağdaki stretch faktörü paneli büzemesin, 700–720 arası dursun.
    panel.setMinimumWidth(700)
    panel.setMaximumWidth(720)
    panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    satir = QHBoxLayout()
    satir.setContentsMargins(0, 0, 0, 0)
    satir.addWidget(panel, 0)
    satir.addStretch(1)
    root.addLayout(satir, 1)
    return content
