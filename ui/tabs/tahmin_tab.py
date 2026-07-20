"""Tahmin sekmesi — geçmiş trendden önerilen, düzenlenebilir varsayımlarla projeksiyon."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from domain.gercek_durum import build_gercek_durum
from domain.mizan_bilanco import tl
from domain.nakit_akis import build_nakit_akis, nakit_bakiye
from domain.tahmin import Tahmin, TahminVarsayim, build_tahmin, oner_varsayim, tahmin_csv
from infra.config import MikroConfig
from infra.mikro_api import MikroClient
from infra.mikro_fetch import (
    fetch_cari_bakiye,
    fetch_nakit_akis_hareket,
    fetch_nakit_delta,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from ui.bilesenler import para_spin, yuzde_spin
from ui.rapor_tab import RaporTab, firma_getir
from ui.tahmin_pdf import export_tahmin_pdf
from ui.tahmin_view import build_tahmin_widget
from ui.worker import IsFonksiyonu


class TahminTab(RaporTab):
    """Geçmiş trendden otomatik önerip kullanıcının düzenlediği ileriye dönük projeksiyon."""

    EMOJI = "🔮"
    BASLIK = "Tahmin"
    ACIKLAMA = (
        "Geçmiş trendden otomatik tahmin üretir; varsayımları (büyüme, marj,<br>"
        "gider) düzenleyip senaryonu görebilirsin: tahmini ciro, kâr ve nakit.<br>"
        "<span style='color:#9aa0a8;'>Önce «Geçmişten Doldur», sonra istediğini değiştir.</span>")
    GETIR_ETIKET = "Geçmişten Doldur"
    BASLARKEN = "Geçmiş veri çekiliyor (satış, marj, nakit, gider)…"
    DONEM_ETIKET = "Geçmiş veri dönemi:"
    TARIH_GENISLIK = 120
    PDF_DESTEK = True
    HERO_ASSET = "empty-tahmin.png"

    _t: Tahmin | None = None

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        # Varsayım formu (senaryo) — düzenlenebilir
        form_box = QFrame()
        form_box.setObjectName("tahminForm")
        form_box.setStyleSheet(
            "QFrame#tahminForm { background: #f7f9fc; border: 1px solid #e3e8ef; border-radius: 10px; }")
        fl = QHBoxLayout(form_box)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(18)
        self._sp_nakit = para_spin()
        self._sp_ciro = para_spin()
        self._sp_gider = para_spin()
        self._sp_buyume = yuzde_spin(-50.0, 100.0)
        self._sp_marj = yuzde_spin(0.0, 100.0)
        self._sp_ufuk = QSpinBox()
        self._sp_ufuk.setRange(1, 36)
        self._sp_ufuk.setValue(12)
        self._sp_ufuk.setSuffix(" ay")
        for etiket, w in (
            ("Başlangıç nakit", self._sp_nakit), ("Baz aylık ciro", self._sp_ciro),
            ("Aylık büyüme", self._sp_buyume), ("Brüt marj", self._sp_marj),
            ("Aylık sabit gider", self._sp_gider), ("Ufuk", self._sp_ufuk),
        ):
            col = QFormLayout()
            col.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(etiket)
            lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            col.addRow(lbl, w)
            fl.addLayout(col)
        self._btn_projekte = QPushButton("Projekte Et")
        self._btn_projekte.clicked.connect(self._on_projekte)
        fl.addWidget(self._btn_projekte)
        layout.addWidget(form_box)

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        ufuk = self._sp_ufuk.value()

        def is_fn(bildir) -> dict[str, Any]:
            client = MikroClient(cfg)
            bildir("Stok hareketleri çekiliyor…")
            stok_rows = fetch_stok_ozet(client, bas, bit)
            stok_aylik = fetch_stok_aylik(client, bas, bit)
            gd = build_gercek_durum(stok_rows=stok_rows, stok_aylik=stok_aylik, bas=bas, bit=bit)
            bildir("Nakit bakiyesi ve hareketleri çekiliyor…")
            kapanis_rows = fetch_cari_bakiye(client, bit)
            baslangic_nakit = nakit_bakiye(kapanis_rows)
            hareket_rows = fetch_nakit_akis_hareket(client, bas, bit)
            donem_delta = fetch_nakit_delta(client, bas, bit)
            na = build_nakit_akis(hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                                  donem_delta=donem_delta, bas=bas, bit=bit)
            bildir("Varsayımlar öneriliyor…")
            satis_serisi = [a.satis for a in gd.trend]
            ay_sayisi = max(1, len(na.aylik))
            sabit_gider = (na.toplam_cikis
                           - na.cikis_kategori.get("Satıcı ödemesi", 0.0)
                           - na.kredi_odeme) / ay_sayisi
            v = oner_varsayim(
                satis_serisi=satis_serisi, brut_marj_yuzde=gd.gercek_brut_marj,
                baslangic_nakit=baslangic_nakit, aylik_sabit_gider=sabit_gider,
                baslangic_ay=bit[:7], ufuk_ay=ufuk,
            )
            return {"varsayim": v, "firma": firma_getir(cfg, client)}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        v: TahminVarsayim = sonuc["varsayim"]
        self._firma = sonuc["firma"]
        self._sp_nakit.setValue(v.baslangic_nakit)
        self._sp_ciro.setValue(v.baz_ciro)
        self._sp_buyume.setValue(v.buyume_yuzde)
        self._sp_marj.setValue(v.marj_yuzde)
        self._sp_gider.setValue(v.sabit_gider)
        self._durum("Geçmişten dolduruldu — varsayımları düzenleyip «Projekte Et»e basabilirsin.", "iyi")
        self._on_projekte()

    def _on_projekte(self) -> None:
        bit = self._donem.bit_tarih()
        v = TahminVarsayim(
            baslangic_ay=f"{bit.year():04d}-{bit.month():02d}",
            baslangic_nakit=self._sp_nakit.value(),
            baz_ciro=self._sp_ciro.value(),
            buyume_yuzde=self._sp_buyume.value(),
            marj_yuzde=self._sp_marj.value(),
            sabit_gider=self._sp_gider.value(),
            ufuk_ay=self._sp_ufuk.value(),
        )
        self._t = build_tahmin(v)
        self._icerik_koy(build_tahmin_widget(self._t, firma=self._firma))
        if self._chrome is not None:
            self._chrome.set_csv_aktif(True)
            self._chrome.set_pdf_aktif(True)
        self._durum(
            f"Tahmin: {self._sp_ufuk.value()} ay · toplam ciro {tl(self._t.toplam_ciro)} · "
            f"dönem sonu nakit {tl(self._t.son_nakit)}",
            "hata" if self._t.en_dusuk_nakit < 0 else "iyi",
        )

    def _on_pdf(self) -> None:
        if not self._t:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"tahmin_{self._t.varsayim.baslangic_ay}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_tahmin_pdf(self._t, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"tahmin_{self._t.varsayim.baslangic_ay}.csv" if self._t else "tahmin.csv"

    def _csv_icerik(self) -> str | None:
        return tahmin_csv(self._t) if self._t else None
