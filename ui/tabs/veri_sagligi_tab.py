"""Veri Sağlığı sekmesi — «bu rapordaki rakamlara güvenebilir miyim?»"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from domain.mizan_bilanco import build_bilanco
from domain.veri_sagligi import (
    KRITIK,
    UYARI,
    Bulgu,
    VeriSagligi,
    build_veri_sagligi,
    veri_sagligi_csv,
)
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError
from infra.mikro_fetch import fetch_mizan, fetch_stok_maliyet_teshis, fetch_stok_ozet
from infra.mukayese_fetch import YilVeritabaniHatasi, donem_satirlari, yil_client
from ui.rapor_tab import RaporTab, firma_getir
from ui.styles import BORDER, MUTED, PANEL_BG
from ui.worker import IsFonksiyonu

_RENK = {
    KRITIK: ("#b91c1c", "#fef2f2", "#fecaca"),
    UYARI: ("#7a5b00", "#fff8e1", "#f0d48a"),
}
_IYI = ("#166534", "#f0fdf4", "#bbf7d0")


class VeriSagligiTab(RaporTab):
    """Rapor rakamlarını bozan veri sorunlarını sade dille listeler."""

    EMOJI = "🩺"
    BASLIK = "Veri Sağlığı"
    ACIKLAMA = (
        "Raporlardaki rakamları bozabilecek kayıt sorunlarını arar:<br>"
        "işlenmemiş maliyet fişi, hatalı stok kaydı, tanınmayan evrak tipi.<br>"
        "<span style='color:#9aa0a8;'>Her bulguda ne olduğu, hangi rakamı etkilediği "
        "ve ne yapılacağı yazar.</span>")
    GETIR_ETIKET = "Veriyi Kontrol Et"
    BASLARKEN = "Kayıtlar kontrol ediliyor…"
    HERO_ASSET = "empty-trendler.png"
    HERO_FIT = "contain"

    _vs: VeriSagligi | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            client = yil_client(cfg, int(bit[:4]))
            okunamayan: list[str] = []

            # Her kaynak AYRI AYRI denenir. Biri düşerse diğerleri yine kontrol edilir;
            # ama düşen kaynak sessizce atlanmaz — «kontrol edilemedi» diye görünür.
            # Bakılamayan bir şeyi temiz sanmak, hatanın kendisinden kötüdür.
            bildir("Muhasebe mizanı kontrol ediliyor…")
            bilanco = None
            try:
                bilanco = build_bilanco(fetch_mizan(client, bit), asof=bit)
            except (MikroAPIError, YilVeritabaniHatasi):
                okunamayan.append("Muhasebe mizanı (kâr ve stok kontrolleri)")

            bildir("Stok hareketleri kontrol ediliyor…")
            stok_rows = None
            try:
                stok_rows = donem_satirlari(cfg, bas, bit, fetch_stok_ozet)
            except (MikroAPIError, YilVeritabaniHatasi):
                okunamayan.append("Stok hareketleri (hatalı kayıt ve evrak tipi)")

            bildir("Satış maliyetleri kontrol ediliyor…")
            maliyet_rows = None
            try:
                maliyet_rows = donem_satirlari(cfg, bas, bit, fetch_stok_maliyet_teshis)
            except (MikroAPIError, YilVeritabaniHatasi):
                okunamayan.append("Satış maliyetleri")

            vs = build_veri_sagligi(
                bas=bas, bit=bit, bilanco=bilanco, stok_rows=stok_rows,
                maliyet_rows=maliyet_rows, okunamayan=okunamayan)
            return {"vs": vs, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        vs: VeriSagligi = sonuc["vs"]
        self._vs = vs
        self._firma = sonuc["firma"]
        self._icerik_koy(_widget(vs))
        self._durum(vs.ozet(),
                    "hata" if vs.kritik else ("uyari" if vs.bulgular else "iyi"))

    def _csv_dosya_adi(self) -> str:
        return f"{self._slug}_{self._vs.bas}_{self._vs.bit}.csv" if self._vs \
            else f"{self._slug}.csv"

    def _csv_icerik(self) -> str | None:
        return veri_sagligi_csv(self._vs) if self._vs else None


def _kart(bulgu: Bulgu) -> QFrame:
    yazi, arka, kenar = _RENK.get(bulgu.onem, (MUTED, PANEL_BG, BORDER))
    kart = QFrame()
    kart.setObjectName("vsKart")
    kart.setStyleSheet(
        f"QFrame#vsKart {{ background: {arka}; border: 1px solid {kenar}; "
        f"border-left: 4px solid {yazi}; border-radius: 10px; }}")
    lay = QVBoxLayout(kart)
    lay.setContentsMargins(16, 13, 16, 14)
    lay.setSpacing(5)

    ust = QLabel(f"{'KRİTİK' if bulgu.onem == KRITIK else 'UYARI'} &nbsp;·&nbsp; "
                 f"{bulgu.baslik}")
    ust.setTextFormat(Qt.TextFormat.RichText)
    ust.setWordWrap(True)
    ust.setStyleSheet(f"color:{yazi}; font-size:14px; font-weight:800; "
                      "background:transparent; border:none;")
    lay.addWidget(ust)

    if bulgu.olcum:
        ol = QLabel(bulgu.olcum)
        ol.setWordWrap(True)
        ol.setStyleSheet(f"color:{yazi}; font-size:12px; font-weight:700; "
                         "background:transparent; border:none;")
        lay.addWidget(ol)

    for etiket, metin in (("Etkisi", bulgu.etkisi), ("Ne yapmalı", bulgu.ne_yapmali)):
        e = QLabel(f"<b>{etiket}:</b> {metin}")
        e.setTextFormat(Qt.TextFormat.RichText)
        e.setWordWrap(True)
        e.setStyleSheet("color:#334155; font-size:12px; background:transparent; "
                        "border:none;")
        lay.addWidget(e)
    return kart


def _widget(vs: VeriSagligi) -> QWidget:
    icerik = QWidget()
    icerik.setObjectName("vsContent")
    icerik.setStyleSheet("QWidget#vsContent { background: transparent; }")
    root = QVBoxLayout(icerik)
    root.setContentsMargins(4, 4, 4, 8)
    root.setSpacing(12)

    yazi, arka, kenar = _IYI if vs.temiz else _RENK.get(
        KRITIK if vs.kritik else UYARI, _IYI)
    ozet = QLabel(vs.ozet())
    ozet.setWordWrap(True)
    ozet.setStyleSheet(
        f"color:{yazi}; background:{arka}; border:1px solid {kenar}; border-radius:10px; "
        "font-size:15px; font-weight:800; padding:14px 16px;")
    root.addWidget(ozet)

    for b in vs.bulgular:
        root.addWidget(_kart(b))

    if vs.okunamayan:
        # Kontrol EDİLEMEYEN alan, temiz çıkan alandan farklıdır; ikisini aynı
        # göstermek kullanıcıya olmayan bir güven verir.
        not_ = QLabel("Kontrol edilemedi: " + " · ".join(vs.okunamayan)
                      + " — bağlantı ya da yetki sorunu olabilir.")
        not_.setWordWrap(True)
        not_.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")
        root.addWidget(not_)

    root.addStretch(1)
    return icerik
