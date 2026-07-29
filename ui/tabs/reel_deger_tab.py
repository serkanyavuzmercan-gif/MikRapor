"""
Reel Değer sekmesi — vadeli satmak neye mal oluyor, vadeli almak ne kazandırıyor?

TEK KONU. Kredi kartı finansman senaryosu Tahmin & Projeksiyon'a taşındı: buradaki dört
değişkenin üçü yalnız en alttaki kart tablosunu besliyordu ve panel bunu söylemiyordu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.mizan_bilanco import tl
from domain.reel_deger import (
    ReelDegerAnalizi,
    ReelDegerVarsayim,
    build_reel_deger_analizi,
    reel_deger_csv,
)
from domain.tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak
from infra.config import MikroConfig
from infra.mikro_fetch import fetch_acik_kalemler, fetch_cari_vade_gun
from infra.mukayese_fetch import yil_client
from ui.bilesenler import varsayilan_kayit_yolu, yuzde_spin
from ui.rapor_tab import RaporTab, firma_getir
from ui.reel_deger_pdf import export_reel_deger_pdf
from ui.reel_deger_view import build_reel_deger_widget
from ui.worker import IsFonksiyonu


class ReelDegerTab(RaporTab):
    """Nominal bakiyeleri değiştirmeden vade/finansman etkisini yorumlar."""

    EMOJI = "💡"
    BASLIK = "Reel Değer"
    ACIKLAMA = (
        "Vadeli satmak size neye mal oluyor, vadeli almak ne kazandırıyor?<br>"
        "Açık alacak ve borçlarınızı vadelerine göre bugünkü değerine çevirir.<br>"
        "<span style='color:#9aa0a8;'>Muhasebe tutarlarını değiştirmez.</span>"
    )
    GETIR_ETIKET = "Reel Değer Analizi"
    BASLARKEN = "Açık alacak ve borç kalemleri çekiliyor…"
    HERO_ASSET = "empty-tahsilat.png"
    PDF_DESTEK = True

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

        for etiket, spin in (
            # TEK DEĞİŞKEN, JARGONSUZ. «Yıllık iskonto / fırsat maliyeti» ders
            # kitabından alınmıştı; kullanıcı «buraya ne yazacağım» sorusunu
            # cevaplayamıyordu. Kredi kartı senaryosu Tahmin'e taşındı.
            ("Paranın size yıllık maliyeti", self._sp_iskonto),
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

        for spin in (self._sp_iskonto,):
            spin.valueChanged.connect(self._varsayim_degisti)

    def _varsayim(self) -> ReelDegerVarsayim:
        return ReelDegerVarsayim(
            yillik_iskonto_yuzde=self._sp_iskonto.value(),
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
            f"vade etkisi {tl(self._analiz.net_vade_etkisi)}",
            "hata" if self._analiz.net_vade_etkisi < -0.005 else "iyi",
        )

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            # Veritabanını firma kodu seçer: dönemin bittiği yıl hangi
            # veritabanındaysa oraya bağlanılır (bkz. infra/veritabani.py).
            client = yil_client(cfg, int(bit[:4]))
            bildir("Cari ödeme planları çekiliyor…")
            vade_gun_map = fetch_cari_vade_gun(client)
            bildir("Açık alacak ve borç kalemleri çekiliyor…")
            acik_rows = fetch_acik_kalemler(client, bit, bas, bit)
            ta = build_tahsilat_alacak(acik_rows, vade_gun_map=vade_gun_map, bas=bas, bit=bit)
            return {"ta": ta, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        self._ta = sonuc["ta"]
        self._firma = sonuc["firma"]
        self._analizi_yenile()

    def _on_pdf(self) -> None:
        if self._analiz is None or self._ta is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"{self._slug}_{self._ta.bit}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_reel_deger_pdf(
                self._analiz, path, bas=self._ta.bas, bit=self._ta.bit, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        if self._ta is None:
            return f"{self._slug}.csv"
        return f"{self._slug}_{self._ta.bit}.csv"

    def _csv_icerik(self) -> str | None:
        return reel_deger_csv(self._analiz) if self._analiz else None
