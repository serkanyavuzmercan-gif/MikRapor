"""Trend & Oranlar sekmesi — aylık fiili trend + bilanço finansal oranları."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.gercek_durum import build_gercek_durum
from domain.mizan_bilanco import build_bilanco, tl
from domain.trend import TrendRapor, build_trend, trend_csv
from infra.config import MikroConfig, load_gercek_durum_ayarlar
from infra.mikro_api import MikroClient
from infra.mikro_fetch import (
    fetch_mizan,
    fetch_nakit_aylik,
    fetch_nakit_ozet,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from ui.rapor_tab import RaporTab, firma_getir
from ui.trend_pdf import export_trend_pdf
from ui.trend_view import build_trend_widget
from ui.worker import IsFonksiyonu


class TrendTab(RaporTab):
    """Aylık operasyonel trend + bilanço oranları sekmesi."""

    EMOJI = "📈"
    BASLIK = "Trend & Oranlar"
    ACIKLAMA = (
        "Dönem içi aylık satış, alış, brüt kâr ve nakit trendini gösterir;<br>"
        "bilanço tarihindeki klasik finansal oranları (cari, asit-test, borç/özkaynak)<br>"
        "yan yana koyar."
    )
    GETIR_ETIKET = "Trend / Oranları Getir"
    BASLARKEN = "Stok, nakit ve mizan çekiliyor…"
    PDF_DESTEK = True

    _tr: TrendRapor | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        ayarlar = load_gercek_durum_ayarlar()

        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Stok hareketleri çekiliyor…")
            stok_rows = fetch_stok_ozet(client, bas, bit)
            stok_aylik = fetch_stok_aylik(client, bas, bit)
            bildir("Banka nakit hareketleri çekiliyor…")
            nakit_rows = fetch_nakit_ozet(client, bas, bit)
            nakit_aylik = fetch_nakit_aylik(client, bas, bit)
            bildir("GL mizan çekiliyor…")
            mizan_rows = fetch_mizan(client, bit)
            bildir("Trend kuruluyor…")
            gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                bas=bas, bit=bit, ayarlar=ayarlar,
            )
            bilanco = build_bilanco(mizan_rows, asof=bit)
            tr = build_trend(aylik=gd.trend, bilanco=bilanco, bas=bas, bit=bit)
            return {"tr": tr, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        tr: TrendRapor = sonuc["tr"]
        self._tr = tr
        self._firma = sonuc["firma"]
        self._icerik_koy(build_trend_widget(tr, firma=self._firma))
        cari = next((o for o in tr.oranlar if o.kod == "cari"), None)
        parts = [
            f"{tr.ay_sayisi} ay",
            f"Satış {tl(tr.toplam_satis)}",
            f"Brüt {tl(tr.toplam_brut)}",
            f"Nakit net {tl(tr.toplam_nakit_net)}",
        ]
        if cari is not None:
            parts.append(f"Cari oran {cari.metin()}")
        if tr.ay_sayisi == 0 and tr.aktif_toplam == 0:
            parts.insert(0, "⚠ veri yok — dönem/yıl kontrol edin")
        self._durum(
            " · ".join(parts),
            "uyari" if tr.ay_sayisi == 0 else "iyi",
        )

    def _on_pdf(self) -> None:
        if not self._tr:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"trend_oranlar_{self._tr.bas}_{self._tr.bit}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_trend_pdf(self._tr, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"trend_oranlar_{self._tr.bas}_{self._tr.bit}.csv" if self._tr else "trend_oranlar.csv"

    def _csv_icerik(self) -> str | None:
        return trend_csv(self._tr) if self._tr else None
