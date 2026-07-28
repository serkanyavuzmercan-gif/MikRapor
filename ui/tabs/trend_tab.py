"""Trend & Oranlar sekmesi — aylık fiili trend + bilanço finansal oranları."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
)

from domain.ai_yorum import YilKapanis, yillar_arasi_csv
from domain.gercek_durum import build_gercek_durum
from domain.mizan_bilanco import build_bilanco, tl
from domain.trend import TrendRapor, build_trend, trend_csv
from infra.config import MikroConfig, load_gercek_durum_ayarlar
from infra.mikro_fetch import fetch_mizan
from infra.mukayese_fetch import (
    donem_hareketleri,
    donem_kapanisi,
    onceki_donem,
    yil_client,
    yil_donemleri,
    yillari_cek,
)
from ui.bilesenler import varsayilan_kayit_yolu
from ui.nav_tip import bagla_nav_tip
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
        "klasik finansal oranları (cari, asit-test, borç/özkaynak) yan yana koyar.<br>"
        "<span style='color:#9aa0a8;'>Tarih aralığını birden çok yıla yayarsanız "
        "TL ve dolar bazlı yıl mukayesesi de eklenir.</span>"
    )
    GETIR_ETIKET = "Trend / Oranları Getir"
    BASLARKEN = "Stok, nakit ve mizan çekiliyor…"
    PDF_DESTEK = True
    HERO_ASSET = "empty-trendler.png"
    HERO_FIT = "contain"

    _tr: TrendRapor | None = None
    _kapanislar: list[YilKapanis] = []

    def _ilk_mesaj(self) -> str:
        return "Hazır"

    def _ust_alan(self, layout: QVBoxLayout) -> None:
        """
        «Geçen yılın aynı dönemi» anahtarı.

        Tarih aralığı kutsal — ama kullanıcı AÇIKÇA isterse geçmiş dönem de gelir.
        Fark şurada: program kendi kafasına göre dışarı çıkmıyor, kullanıcı istediği
        için çıkıyor ve ne geldiği sütun başlığında yazıyor.

        Buna ihtiyaç var çünkü takvim yılına bölünmüş sütunlar farklı uzunlukta olabilir:
        canlıda 2025 sütunu 5 ay, 2026 sütunu 7 aydı ve tablo «%+4 büyüme» gösteriyordu —
        aylığa indirilince satış %25 DÜŞMÜŞTÜ. Aynı uzunlukta iki pencere olmadan akış
        kalemleri kıyaslanamaz.
        """
        self._chk_gecen_yil = QCheckBox("Geçen yılın aynı dönemiyle karşılaştır")
        self._chk_gecen_yil.setObjectName("trGecenYil")
        self._chk_gecen_yil.setCursor(Qt.CursorShape.PointingHandCursor)
        # QSS verilince Qt tüm çizimi stil sayfasına devreder; ::indicator kuralı yoksa
        # kutucuk komple kaybolur (ai onay kutusunda canlıda yaşandı).
        self._chk_gecen_yil.setStyleSheet(
            "QCheckBox#trGecenYil { color:#475569; font-size:12px; spacing:8px; "
            "background:transparent; margin: 0 0 8px 2px; }"
            "QCheckBox#trGecenYil::indicator { width:14px; height:14px; "
            "border:2px solid #94a3b8; border-radius:4px; background:#ffffff; }"
            "QCheckBox#trGecenYil::indicator:hover { border-color:#0f766e; }"
            "QCheckBox#trGecenYil::indicator:checked { background:#0f766e; "
            "border-color:#0f766e; }")
        bagla_nav_tip(
            self._chk_gecen_yil,
            "Mukayese tablosu, seçtiğiniz dönemi bir yıl öncesinin AYNI dönemiyle "
            "yan yana koyar. İki sütun eşit uzunlukta olduğu için satış ve kâr "
            "gerçekten kıyaslanabilir.",
            eyebrow="MUKAYESE", parent=self)
        layout.addWidget(self._chk_gecen_yil)

    def _is_hazirla(self, cfg: MikroConfig, bas: str, bit: str) -> IsFonksiyonu:
        ayarlar = load_gercek_durum_ayarlar()
        # Widget durumu GUI iş parçacığında okunur; worker'a sade bir bool gider.
        gecen_yil = self._chk_gecen_yil.isChecked()

        def is_fn(bildir) -> dict[str, Any]:
            bit_client = yil_client(cfg, int(bit[:4]))
            bildir("Stok ve banka hareketleri çekiliyor…")
            stok_rows, stok_aylik, nakit_rows, nakit_aylik = donem_hareketleri(
                cfg, bas, bit, bildir=bildir)
            bildir("GL mizan çekiliyor…")
            mizan_rows = fetch_mizan(bit_client, bit)
            bildir("Trend kuruluyor…")
            gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                bas=bas, bit=bit, ayarlar=ayarlar,
            )
            # GRAFİK DE SEÇİLİ DÖNEMİ GÖSTERİR. Eskiden kısa dönemde grafik 12 aya
            # genişletiliyordu («3 aylık dönemde 3 çubuk trend sayılmaz» diye); ama bu,
            # kullanıcının seçmediği ayları ekrana koyuyordu. Seçim kutsal: dönem üç
            # aysa grafik üç ay gösterir.
            bilanco = build_bilanco(mizan_rows, asof=bit)
            tr = build_trend(aylik=gd.trend, bilanco=bilanco, bas=bas, bit=bit)

            kapanislar: list[YilKapanis] = []
            if gecen_yil:
                # KULLANICI AÇIKÇA İSTEDİ: seçili dönem + bir yıl öncesinin aynı dönemi.
                # İki sütun eşit uzunlukta, o yüzden akış kalemleri kıyaslanabilir.
                o_bas, o_bit = onceki_donem(bas, bit)
                kapanislar = [k for k in (
                    donem_kapanisi(cfg, o_bas, o_bit, bildir=bildir),
                    donem_kapanisi(cfg, bas, bit, client=bit_client, bildir=bildir),
                ) if k is not None]
            elif len(yil_donemleri(bas, bit)) > 1:
                # Varsayılan: SEÇİLEN ARALIĞIN yıllara bölünmüş hâli. Her sütun o yılın
                # aralıkla kesişimi kadar okunur, aralık dışından tek gün alınmaz.
                kapanislar = yillari_cek(
                    cfg, bas, bit, odak_client=bit_client, bildir=bildir)

            return {"tr": tr, "firma": firma_getir(cfg, bit_client),
                    "kapanislar": kapanislar}

        return is_fn

    def _goster(self, sonuc: dict[str, Any]) -> None:
        tr: TrendRapor = sonuc["tr"]
        self._tr = tr
        self._firma = sonuc["firma"]
        self._kapanislar = sonuc.get("kapanislar") or []
        self._icerik_koy(build_trend_widget(
            tr, firma=self._firma, kapanislar=self._kapanislar))
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
            self, "PDF Kaydet",
            varsayilan_kayit_yolu(f"{self._slug}_{self._tr.bas}_{self._tr.bit}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            export_trend_pdf(self._tr, path, firma=self._firma,
                             kapanislar=self._kapanislar)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._durum(f"PDF kaydedildi: {Path(path).name}", "iyi")

    def _csv_dosya_adi(self) -> str:
        return f"{self._slug}_{self._tr.bas}_{self._tr.bit}.csv" if self._tr else f"{self._slug}.csv"

    def _csv_icerik(self) -> str | None:
        if not self._tr:
            return None
        csv = trend_csv(self._tr)
        mukayese = yillar_arasi_csv(self._kapanislar)
        return f"{csv}\r\n\r\nYILLAR ARASI MUKAYESE\r\n{mukayese}" if mukayese else csv
