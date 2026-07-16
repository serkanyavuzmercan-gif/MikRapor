"""Gelir Tablosu sekmesi — dönem (başlangıç–bitiş) kâr/zarar şelalesi."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.gelir_tablosu import GelirTablosu, build_gelir_tablosu, gelir_tablosu_csv
from domain.mizan_bilanco import tl
from domain.ortak import yuzde
from infra.config import MikroConfig
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_gelir_tablosu
from ui.gelir_tablosu_pdf import export_gelir_tablosu_pdf
from ui.gelir_tablosu_view import build_gelir_tablosu_widget
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu


class GelirTablosuTab(RaporTab):
    """Dönem (başlangıç–bitiş) gelir tablosu üreten bağımsız rapor sekmesi."""

    EMOJI = "📈"
    BASLIK = "Gelir Tablosu"
    ACIKLAMA = ("Seçtiğiniz dönemde satış, maliyet ve giderlerden<br>"
                "kâr/zararın nasıl oluştuğunu gösterir.")
    GETIR_ETIKET = "Gelir Tablosu Getir"
    BASLARKEN = "Dönem gelir/gider hareketleri çekiliyor…"
    PDF_DESTEK = True

    _gt: GelirTablosu | None = None

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Dönem gelir/gider hareketleri çekiliyor…")
            rows = fetch_gelir_tablosu(client, bas, bit)
            bildir("Gelir tablosu kuruluyor…")
            gt = build_gelir_tablosu(rows, bas=bas, bit=bit)
            return {"gt": gt, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        gt: GelirTablosu = sonuc["gt"]
        self._gt = gt
        self._firma = sonuc["firma"]
        self._icerik_koy(build_gelir_tablosu_widget(gt, firma=self._firma))
        self._durum(
            f"{gt.hesap_sayisi} gelir/gider hesabı · Net Kâr {tl(gt.net_kar)} "
            f"(net marj {yuzde(gt.net_marj)})",
            "iyi" if gt.net_kar >= 0 else "hata",
        )

    def _on_pdf(self) -> None:
        if not self._gt:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"gelir_tablosu_{self._gt.bas}_{self._gt.bit}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_gelir_tablosu_pdf(self._gt, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001 — kullanıcıya göster
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"gelir_tablosu_{self._gt.bas}_{self._gt.bit}.csv" if self._gt else "gelir_tablosu.csv"

    def _csv_icerik(self) -> str | None:
        return gelir_tablosu_csv(self._gt) if self._gt else None
