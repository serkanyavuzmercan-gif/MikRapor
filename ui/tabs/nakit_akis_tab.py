"""Nakit Akış sekmesi — banka/kasa hareketinden kategorize nakit akış."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.kredi import KrediOzet, kredi_ozet, taksitleri_derle
from domain.mizan_bilanco import tl
from domain.nakit_akis import NakitAkis, build_nakit_akis, nakit_akis_csv
from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import (
    fetch_cari_bakiye,
    fetch_kredi_gl,
    fetch_kredi_taksitleri,
    fetch_nakit_akis_hareket,
    fetch_nakit_delta,
)
from ui.bilesenler import varsayilan_kayit_yolu
from ui.nakit_akis_pdf import export_nakit_akis_pdf
from ui.nakit_akis_view import build_nakit_akis_widget
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu


class NakitAkisTab(RaporTab):
    """Banka/kasa hareketinden kategorize nakit akış (tahsilat, ödeme, kredi…) sekmesi."""

    EMOJI = "💵"
    BASLIK = "Nakit Akış"
    ACIKLAMA = (
        "Banka ve kasadan fiilen geçen para — karşı tarafına göre kategorize:<br>"
        "müşteri tahsilatı, satıcı ödemesi, kredi kullanım/ödemesi, vergi & SGK.<br>"
        "<span style='color:#9aa0a8;'>Açılış → girişler − çıkışlar → kapanış + aylık trend.</span>")
    GETIR_ETIKET = "Nakit Akışı Getir"
    BASLARKEN = "Banka/kasa hareketleri çekiliyor…"
    PDF_DESTEK = True
    HERO_ASSET = "empty-nakit.png"

    _na: NakitAkis | None = None

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Banka/kasa hareketleri çekiliyor…")
            hareket_rows = fetch_nakit_akis_hareket(client, bas, bit)
            bildir("Kapanış bakiyeleri çekiliyor…")
            kapanis_rows = fetch_cari_bakiye(client, bit)
            donem_delta = fetch_nakit_delta(client, bas, bit)
            bildir("Nakit akış kuruluyor…")
            na = build_nakit_akis(
                hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                donem_delta=donem_delta, bas=bas, bit=bit)
            # Banka hareketlerinde kredi hiç görünmüyorsa muhasebeden (300/303) yedek al —
            # kredi taksitleri birçok kurulumda cari harekete değil doğrudan GL'ye işlenir.
            if na.kredi_odeme < 0.005 and na.kredi_kullanim < 0.005:
                try:
                    bildir("Kredi hareketi muhasebeden okunuyor…")
                    kgl = fetch_kredi_gl(client, bas, bit)
                    na.kredi_odeme_gl = kgl.get("odeme", 0.0)
                    na.kredi_kullanim_gl = kgl.get("kullanim", 0.0)
                except MikroAPIError:
                    pass
            # Yaklaşan (ödenmemiş) kredi taksitleri — takvimden
            kredi: KrediOzet | None = None
            try:
                bildir("Kredi taksit takvimi çekiliyor…")
                taksitler = taksitleri_derle(fetch_kredi_taksitleri(client, ay_ileri=18))
                if taksitler:
                    kredi = kredi_ozet(taksitler, en_fazla=8)
            except MikroAPIError:
                kredi = None
            return {"na": na, "firma": firma_getir(cfg, client), "kredi": kredi}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        na: NakitAkis = sonuc["na"]
        self._na = na
        self._firma = sonuc["firma"]
        self._icerik_koy(build_nakit_akis_widget(
            na, firma=self._firma, kredi=sonuc.get("kredi")))
        parts = [
            f"Giriş {tl(na.toplam_giris)}",
            f"Çıkış {tl(na.toplam_cikis)}",
            f"Net {tl(na.net_akis)}",
        ]
        if na.kredi_odeme_gosterim > 0.005 or na.kredi_kullanim_gosterim > 0.005:
            kaynak = " (muhasebeden)" if na.kredi_kaynak_gl else ""
            parts.append(f"Kredi net {tl(na.kredi_net_gosterim)}{kaynak}")
        if na.hareket_sayisi == 0:
            parts.insert(0, "⚠ banka/kasa hareketi yok — dönem/yıl kontrol edin")
        self._durum(
            " · ".join(parts),
            "uyari" if na.hareket_sayisi == 0 else ("iyi" if na.net_akis >= 0 else "hata"),
        )

    def _on_pdf(self) -> None:
        if not self._na:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"nakit_akis_{self._na.bas}_{self._na.bit}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_nakit_akis_pdf(self._na, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"nakit_akis_{self._na.bas}_{self._na.bit}.csv" if self._na else "nakit_akis.csv"

    def _csv_icerik(self) -> str | None:
        return nakit_akis_csv(self._na) if self._na else None
