"""Anında Bilanço sekmesi — tarih itibarıyla mizan → bilanço."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from domain.mizan_bilanco import Bilanco, bilanco_csv, build_bilanco
from infra.config import MikroConfig
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_mizan
from ui.bilanco_pdf import export_bilanco_pdf
from ui.bilanco_view import build_bilanco_widget
from ui.rapor_tab import RaporTab, firma_getir
from ui.worker import IsFonksiyonu


class BilancoTab(RaporTab):
    """Tarih itibarıyla bilanço üreten bağımsız rapor sekmesi."""

    EMOJI = "📊"
    BASLIK = "Anında Bilanço"
    ACIKLAMA = "Mikro Genel Muhasebe verilerinizden TDHP formatında bilanço oluşturun."
    IPUCU = ""
    GETIR_ETIKET = "Bilanço Getir"
    BASLARKEN = "GL mizan çekiliyor…"
    DONEM_ETIKET = "Tarih itibarıyla:"
    TEK_TARIH = True
    PDF_DESTEK = True

    _bilanco: Bilanco | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        asof = bit

        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir(f"{asof} itibarıyla GL mizan çekiliyor…")
            rows = fetch_mizan(client, asof)
            bildir("Bilanço kuruluyor…")
            b = build_bilanco(rows, asof=asof)
            return {"bilanco": b, "firma": firma_getir(cfg, client), "hesap_sayisi": len(rows)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        b: Bilanco = sonuc["bilanco"]
        self._bilanco = b
        self._firma = sonuc["firma"]
        self._icerik_koy(build_bilanco_widget(b, firma=self._firma))
        n = sonuc["hesap_sayisi"]
        if abs(b.fark) < 1.0:
            self._durum(f"{n} hesap · Aktif=Pasif ✓ dengede.", "iyi")
        elif b.dengede:
            self._durum(f"{n} hesap · ≈ dengede (kalan %{b.denge_yuzde:.2f}).", "uyari")
        else:
            self._durum(f"{n} hesap · FARK var (%{b.denge_yuzde:.2f}).", "hata")

    def _on_pdf(self) -> None:
        if not self._bilanco:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"bilanco_{self._bilanco.asof}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_bilanco_pdf(self._bilanco, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001 — kullanıcıya göster
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"bilanco_{self._bilanco.asof}.csv" if self._bilanco else "bilanco.csv"

    def _csv_icerik(self) -> str | None:
        return bilanco_csv(self._bilanco) if self._bilanco else None
