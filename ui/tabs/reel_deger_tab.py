"""Reel Değer & Finansman sekmesi — vade etkisi ve kart finansman senaryosu."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from domain.kredi import KART_BORCU_VARSAYILAN_ODEME_YUZDE, kredi_karti_borclarini_derle
from domain.mizan_bilanco import tl
from domain.reel_deger import (
    ReelDegerAnalizi,
    ReelDegerVarsayim,
    build_reel_deger_analizi,
    reel_deger_csv,
)
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak
from infra.config import MikroConfig
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_acik_kalemler, fetch_cari_vade_gun, fetch_kredi_karti_borclari
from ui.bilesenler import para_spin, yuzde_spin
from ui.rapor_tab import RaporTab, firma_getir
from ui.reel_deger_view import build_reel_deger_widget
from ui.worker import IsFonksiyonu


class ReelDegerTab(RaporTab):
    """Nominal bakiyeleri değiştirmeden vade/finansman etkisini yorumlar."""

    EMOJI = "💡"
    BASLIK = "Reel Değer"
    ACIKLAMA = (
        "Açık alacak ve borçların vade yapısını, seçtiğiniz iskonto oranıyla bugünkü ekonomik<br>"
        "değere çevirir. Kredi kartı borcunun kısmi ödenmesi halinde oluşabilecek finansman<br>"
        "maliyetini de ayrı gösterir; muhasebe tutarlarını değiştirmez."
    )
    GETIR_ETIKET = "Reel Değer Analizi"
    BASLARKEN = "Açık alacak, borç ve kart bakiyeleri çekiliyor…"
    HERO_ASSET = "empty-tahsilat.png"

    _ta: TahsilatAlacak | None = None
    _analiz: ReelDegerAnalizi | None = None

    def _ilk_mesaj(self) -> str:
        return "Varsayımları ayarlayıp analizi getirin."

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("reelVarsayimBar")
        bar.setStyleSheet(
            "QFrame#reelVarsayimBar { background:#f7fafc; border:1px solid #d9e2ec; "
            "border-radius:10px; margin: 0 0 8px 0; }"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.setSpacing(12)

        baslik = QLabel("ANALİZ VARSAYIMLARI")
        baslik.setStyleSheet("color:#1f3a5f; font-size:11px; font-weight:800; background:transparent;")
        lay.addWidget(baslik)

        self._sp_iskonto = yuzde_spin(0.0, 250.0)
        self._sp_iskonto.setValue(45.0)
        self._sp_kart_faiz = yuzde_spin(0.0, 30.0)
        self._sp_kart_faiz.setValue(4.0)
        self._sp_kart_odeme = yuzde_spin(0.0, 100.0)
        self._sp_kart_odeme.setValue(KART_BORCU_VARSAYILAN_ODEME_YUZDE)
        self._sp_kart_borc = para_spin()
        self._sp_kart_borc.setReadOnly(True)

        for etiket, spin in (
            ("Yıllık iskonto / fırsat maliyeti", self._sp_iskonto),
            ("Kart aylık finansman maliyeti", self._sp_kart_faiz),
            ("Kart aylık ödeme oranı", self._sp_kart_odeme),
            ("Açık kart borcu (canlı)", self._sp_kart_borc),
        ):
            grup = QWidget()
            gl = QVBoxLayout(grup)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setSpacing(2)
            lbl = QLabel(etiket)
            lbl.setStyleSheet("color:#526579; font-size:10px; background:transparent;")
            gl.addWidget(lbl)
            spin.setMinimumWidth(130)
            spin.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            gl.addWidget(spin)
            lay.addWidget(grup)

        bilgi = QLabel("Varsayımlar yalnızca bu karar destek analizini etkiler.")
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("color:#7b8794; font-size:10.5px; background:transparent;")
        lay.addWidget(bilgi, 1)
        layout.addWidget(bar)

        for spin in (self._sp_iskonto, self._sp_kart_faiz, self._sp_kart_odeme):
            spin.valueChanged.connect(self._varsayim_degisti)

    def _varsayim(self) -> ReelDegerVarsayim:
        return ReelDegerVarsayim(
            yillik_iskonto_yuzde=self._sp_iskonto.value(),
            kart_aylik_faiz_yuzde=self._sp_kart_faiz.value(),
            kart_odeme_yuzde=self._sp_kart_odeme.value(),
            kart_borcu_acik=self._sp_kart_borc.value(),
        )

    def _varsayim_degisti(self, _deger: float) -> None:
        if self._ta is None:
            return
        self._analizi_yenile()

    def _analizi_yenile(self) -> None:
        if self._ta is None:
            return
        self._analiz = build_reel_deger_analizi(self._ta, self._varsayim())
        self._icerik_koy(build_reel_deger_widget(
            self._analiz, bas=self._ta.bas, bit=self._ta.bit, firma=self._firma))
        self._durum(
            f"Reel net pozisyon {tl(self._analiz.reel_net_pozisyon)} · "
            f"kart finansman maliyeti {tl(self._analiz.kart.toplam_finansman_maliyeti)}",
            "hata" if self._analiz.net_vade_etkisi < -0.005 else "iyi",
        )

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Cari ödeme planları çekiliyor…")
            vade_gun_map = fetch_cari_vade_gun(client)
            bildir("Açık alacak ve borç kalemleri çekiliyor…")
            acik_rows = fetch_acik_kalemler(client, bit, bas, bit)
            ta = build_tahsilat_alacak(acik_rows, vade_gun_map=vade_gun_map, bas=bas, bit=bit)
            bildir("Açık kredi kartı borçları çekiliyor…")
            kart_borclari = kredi_karti_borclarini_derle(fetch_kredi_karti_borclari(client, bit))
            return {
                "ta": ta,
                "kart_borcu": sum(k.borc for k in kart_borclari),
                "firma": firma_getir(cfg, client),
            }

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        self._ta = sonuc["ta"]
        self._firma = sonuc["firma"]
        self._sp_kart_borc.setValue(float(sonuc.get("kart_borcu", 0.0)))
        self._analizi_yenile()

    def _csv_dosya_adi(self) -> str:
        if self._ta is None:
            return f"{self._slug}.csv"
        return f"{self._slug}_{self._ta.bit}.csv"

    def _csv_icerik(self) -> str | None:
        return reel_deger_csv(self._analiz) if self._analiz else None
