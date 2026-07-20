"""Nakit & Kârlılık sekmesi — fiili stok + banka hareketinden operasyonel durum."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.gelir_tablosu import build_gelir_tablosu
from domain.gercek_durum import GercekDurum, build_gercek_durum, gercek_durum_csv
from domain.mizan_bilanco import build_bilanco, tl
from domain.ortak import yuzde
from infra.config import MikroConfig, load_gercek_durum_ayarlar
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import (
    fetch_cari_bakiye,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_aylik,
    fetch_nakit_ozet,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from ui.gercek_durum_pdf import export_gercek_durum_pdf
from ui.gercek_durum_settings_dialog import GercekDurumAyarlarDialog
from ui.gercek_durum_view import build_gercek_durum_widget
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu


class GercekDurumTab(RaporTab):
    """Fiili stok + banka hareketinden nakit & kârlılık üreten bağımsız rapor sekmesi."""

    EMOJI = "💰"
    BASLIK = "Nakit & Kârlılık"
    ACIKLAMA = (
        "Faturalar muhasebeleştirilmeden, deponuzdan geçen mal ve bankadan geçen "
        "para üzerinden işletmenin fiili brüt marjını, nakit akışını ve işletme "
        "sermayesini gösterir; resmi gelir tablosuyla mutabakatını yapar."
    )
    GETIR_ETIKET = "Analizi Getir"
    BASLARKEN = "Stok, banka ve bakiye hareketleri çekiliyor…"
    PDF_DESTEK = True
    HERO_ASSET = "empty-nakit-kar.png"

    EKSTRA_ETIKET = "Hesaplama"

    _gd: GercekDurum | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _on_ekstra(self) -> None:
        self._on_ayarlar()

    def _on_ayarlar(self) -> None:
        dlg = GercekDurumAyarlarDialog(self)
        if dlg.exec():
            a = dlg.ayarlar()
            self._durum(f"Ayarlar kaydedildi — {a.ozet()}", "iyi")

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
            bildir("Cari bakiyeler çekiliyor…")
            cari_bakiye_rows = fetch_cari_bakiye(client, bit)
            bildir("GL mizan çekiliyor…")
            mizan_rows = fetch_mizan(client, bit)
            bilanco = build_bilanco(mizan_rows, asof=bit)
            # Resmi GL (karşılaştırma için) — başarısız olsa da rapor üretilir.
            try:
                bildir("Resmi gelir tablosu çekiliyor…")
                gt = build_gelir_tablosu(fetch_gelir_tablosu(client, bas, bit), bas=bas, bit=bit)
            except MikroAPIError:
                gt = None
            bildir("Rapor kuruluyor…")
            gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                cari_bakiye_rows=cari_bakiye_rows,
                bilanco=bilanco, gelir_tablosu=gt,
                bas=bas, bit=bit, ayarlar=ayarlar,
            )
            return {"gd": gd, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        gd: GercekDurum = sonuc["gd"]
        self._gd = gd
        self._firma = sonuc["firma"]
        self._icerik_koy(build_gercek_durum_widget(gd, firma=self._firma))
        parts = [
            f"Stok {gd.stok_kirilim_sayisi} kırılım ({gd.stok_hareket_adet:,} hareket)".replace(",", "."),
            f"Fiili brüt marj {yuzde(gd.gercek_brut_marj)}",
            f"Net nakit {tl(gd.nakit_net)}",
        ]
        if gd.ayar_ozet:
            parts.append(gd.ayar_ozet)
        if gd.cari_hesap_sayisi:
            parts.append(f"Cari {gd.cari_hesap_sayisi} hesap · alacak {tl(gd.alacak)} · borç {tl(gd.borc)}")
        if gd.stok_kirilim_sayisi == 0:
            parts.insert(0, "⚠ stok verisi yok — dönem/yıl kontrol edin")
        self._durum(
            " · ".join(parts),
            "uyari" if gd.veri_eksik else ("iyi" if gd.gercek_brut_kar >= 0 else "hata"),
        )

    def _on_pdf(self) -> None:
        if not self._gd:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"nakit_karlilik_{self._gd.bas}_{self._gd.bit}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_gercek_durum_pdf(self._gd, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"nakit_karlilik_{self._gd.bas}_{self._gd.bit}.csv" if self._gd else "nakit_karlilik.csv"

    def _csv_icerik(self) -> str | None:
        return gercek_durum_csv(self._gd) if self._gd else None
