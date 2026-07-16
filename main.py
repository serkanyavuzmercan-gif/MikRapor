#!/usr/bin/env python3
"""
MikRapor — Mikro ERP finansal raporlama (PyQt6).

Sekmeli mimari: her finansal rapor kendi sekmesinde, kendi içinde bağımsız. İlk sekme
"Anında Bilanço" (Mikro GL'den tarih itibarıyla mizan→bilanço). Gelir Tablosu, Trend, oranlar
gibi raporlar ileride ayrı sekme olarak eklenir (BilancoTab desenini izleyerek).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QDate, QObject, Qt, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bilanco_pdf import export_bilanco_pdf
from bilanco_view import build_bilanco_widget
from config import load_config
from gelir_tablosu import GelirTablosu, build_gelir_tablosu, gelir_tablosu_csv, yuzde
from gelir_tablosu_pdf import export_gelir_tablosu_pdf
from gelir_tablosu_view import build_gelir_tablosu_widget
from gercek_durum import GercekDurum, build_gercek_durum, gercek_durum_csv
from gercek_durum_ayarlar import load_gercek_durum_ayarlar
from gercek_durum_settings_dialog import GercekDurumAyarlarDialog
from gercek_durum_view import build_gercek_durum_widget
from mikro_api import MikroAPIError, MikroClient
from mikro_fetch import (
    fetch_acik_kalemler,
    fetch_cari_bakiye,
    fetch_cari_vade_gun,
    fetch_firma_adi,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_akis_hareket,
    fetch_nakit_delta,
    fetch_nakit_aylik,
    fetch_nakit_ozet,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from tahsilat_alacak import TahsilatAlacak, build_tahsilat_alacak, tahsilat_alacak_csv
from tahsilat_alacak_view import build_tahsilat_alacak_widget
from nakit_akis import NakitAkis, build_nakit_akis, nakit_akis_csv, _nakit_bakiye
from nakit_akis_view import build_nakit_akis_widget
from tahmin import Tahmin, TahminVarsayim, build_tahmin, oner_varsayim, tahmin_csv
from tahmin_view import build_tahmin_widget
from mikro_settings_dialog import MikroAyarlarDialog
from mizan_bilanco import Bilanco, bilanco_csv, build_bilanco, tl
from resources import app_icon, app_logo_pixmap
from empty_state import build_empty_state
from styles import APP_STYLESHEET, BAD, MUTED, OK, WARN
from tarih_secici import TarihSecici

INSTANCE_KEY = "MercanSoftware.MikRapor.SingleInstance"


# ---------------------------------------------------------------------------
# Tek örnek (single instance)
# ---------------------------------------------------------------------------

def _try_activate_existing_instance() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_KEY)
    if not socket.waitForConnected(500):
        return False
    socket.write(b"activate")
    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


def _bring_to_front(window: QMainWindow) -> None:
    if window.isMinimized():
        window.showNormal()
    window.show()
    window.raise_()
    window.activateWindow()


def _start_single_instance_server(window: QMainWindow) -> QLocalServer:
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    server.listen(INSTANCE_KEY)

    def _on_new():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.waitForReadyRead(300)
            conn.readAll()
            conn.disconnectFromServer()
            _bring_to_front(window)

    server.newConnection.connect(_on_new)
    return server


# ---------------------------------------------------------------------------
# Sekmeler arası ortak dönem (bas / bit)
# ---------------------------------------------------------------------------

class DonemDurumu(QObject):
    """Tüm rapor sekmelerinde paylaşılan dönem. Bilanço bitiş tarihi = bit."""

    degisti = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        yil = load_config().calisma_yili or QDate.currentDate().year()
        self._bas = QDate(yil, 1, 1)
        bugun = QDate.currentDate()
        self._bit = QDate(yil, 12, 31) if bugun.year() > yil else bugun

    def bas_tarih(self) -> QDate:
        return self._bas

    def bit_tarih(self) -> QDate:
        return self._bit

    def donem_ayarla(
        self,
        *,
        bas: QDate | None = None,
        bit: QDate | None = None,
        bitis_tek: QDate | None = None,
    ) -> None:
        """bitis_tek: bilanço tek tarihi → bit; bas = o yılın 1 Ocak."""
        if bitis_tek is not None:
            yeni_bit = bitis_tek
            yeni_bas = QDate(bitis_tek.year(), 1, 1)
        else:
            yeni_bas = bas if bas is not None else self._bas
            yeni_bit = bit if bit is not None else self._bit
        if yeni_bas == self._bas and yeni_bit == self._bit:
            return
        self._bas, self._bit = yeni_bas, yeni_bit
        self.degisti.emit()


def _donem_aralik_bagla(tab: QWidget, donem: DonemDurumu, bas: TarihSecici, bit: TarihSecici) -> None:
    """İki tarihli sekmeyi ortak döneme bağlar (Gelir Tablosu, Nakit & Kârlılık)."""
    tab._donem_uzaktan = False  # noqa: SLF001

    def uygula() -> None:
        tab._donem_uzaktan = True  # noqa: SLF001
        bas.blockSignals(True)
        bit.blockSignals(True)
        bas.setDate(donem.bas_tarih())
        bit.setDate(donem.bit_tarih())
        bas.blockSignals(False)
        bit.blockSignals(False)
        tab._donem_uzaktan = False  # noqa: SLF001

    def yayinla() -> None:
        if tab._donem_uzaktan:  # noqa: SLF001
            return
        donem.donem_ayarla(bas=bas.date(), bit=bit.date())

    donem.degisti.connect(uygula)
    bas.dateChanged.connect(lambda _d: yayinla())
    bit.dateChanged.connect(lambda _d: yayinla())
    uygula()


def _donem_tek_bagla(tab: QWidget, donem: DonemDurumu, tarih: TarihSecici) -> None:
    """Tek tarihli bilanço sekmesini ortak dönemin bitişine bağlar."""
    tab._donem_uzaktan = False  # noqa: SLF001

    def uygula() -> None:
        tab._donem_uzaktan = True  # noqa: SLF001
        tarih.blockSignals(True)
        tarih.setDate(donem.bit_tarih())
        tarih.blockSignals(False)
        tab._donem_uzaktan = False  # noqa: SLF001

    def yayinla() -> None:
        if tab._donem_uzaktan:  # noqa: SLF001
            return
        donem.donem_ayarla(bitis_tek=tarih.date())

    donem.degisti.connect(uygula)
    tarih.dateChanged.connect(lambda _d: yayinla())
    uygula()


# ---------------------------------------------------------------------------
# Anında Bilanço sekmesi
# ---------------------------------------------------------------------------

class BilancoTab(QWidget):
    """Tarih itibarıyla bilanço üreten bağımsız rapor sekmesi."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._bilanco: Bilanco | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(10)
        controls.addWidget(QLabel("Tarih itibarıyla:"))
        self._date = TarihSecici(self._donem.bit_tarih(), genislik=140)
        controls.addWidget(self._date)
        _donem_tek_bagla(self, self._donem, self._date)

        self._btn_getir = QPushButton("Bilanço Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_pdf = QPushButton("PDF Kaydet")
        self._btn_pdf.setObjectName("ghostBtn")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_pdf)
        controls.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Tarih seçip «Bilanço Getir»e basın.")
        self._status.setObjectName("toolbarHint")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        self._empty = build_empty_state(
            "Anında Bilanço",
            "Mikro genel muhasebe verinizden, seçtiğiniz tarih itibarıyla "
            "TDHP bilançosunu saniyeler içinde üretir.",
            cta_hint="Bilanço Getir",
        )
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _selected_asof(self) -> str:
        return self._date.date().toString("yyyy-MM-dd")

    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return

        asof = self._selected_asof()
        self._btn_getir.setEnabled(False)
        self._status.setText(f"{self._date.date().toString('dd.MM.yyyy')} itibarıyla GL çekiliyor…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            rows = fetch_mizan(client, asof)
            self._bilanco = build_bilanco(rows, asof=asof)
            # Firma ünvanı: elle girilmişse o kazanır, boşsa Mikro'dan (FIRMALAR.fir_unvan) çek.
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Bilanço getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        b = self._bilanco
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_bilanco_widget(b, firma=self._firma))
        self._btn_pdf.setEnabled(True)
        self._btn_csv.setEnabled(True)
        if abs(b.fark) < 1.0:
            self._status.setText(f"{len(rows)} hesap · Aktif=Pasif ✓ dengede.")
            self._status.setStyleSheet(f"color: {OK};")
        elif b.dengede:
            self._status.setText(f"{len(rows)} hesap · ≈ dengede (kalan %{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet(f"color: {WARN};")
        else:
            self._status.setText(f"{len(rows)} hesap · FARK var (%{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet(f"color: {BAD};")

    def _on_pdf(self) -> None:
        if not self._bilanco:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"bilanco_{self._bilanco.asof}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_bilanco_pdf(self._bilanco, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._status.setText(f"PDF kaydedildi: {Path(path).name}")
        self._status.setStyleSheet(f"color: {OK};")

    def _on_csv(self) -> None:
        if not self._bilanco:
            return
        _csv_kaydet(self, self._status, f"bilanco_{self._bilanco.asof}.csv",
                    bilanco_csv(self._bilanco))


def _csv_kaydet(parent: QWidget, status: QLabel, varsayilan_ad: str, icerik: str) -> None:
    """Ortak CSV kaydetme: dosya seç → UTF-8 (BOM, TR Excel uyumlu) yaz → durumu güncelle."""
    path, _ = QFileDialog.getSaveFileName(parent, "CSV Kaydet", varsayilan_ad, "CSV (*.csv)")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(icerik)
    except OSError as exc:
        QMessageBox.critical(parent, "CSV Hatası", str(exc))
        return
    status.setText(f"CSV kaydedildi: {Path(path).name}")
    status.setStyleSheet(f"color: {OK};")


class GelirTablosuTab(QWidget):
    """Dönem (başlangıç–bitiş) gelir tablosu üreten bağımsız rapor sekmesi."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._gt: GelirTablosu | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        self._bas = TarihSecici(self._donem.bas_tarih(), genislik=130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = TarihSecici(self._donem.bit_tarih(), genislik=130)
        controls.addWidget(self._bit)
        _donem_aralik_bagla(self, self._donem, self._bas, self._bit)

        self._btn_getir = QPushButton("Gelir Tablosu Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)
        self._btn_pdf = QPushButton("PDF Kaydet")
        self._btn_pdf.setObjectName("ghostBtn")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_pdf)
        controls.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Gelir Tablosu Getir»e basın.")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        self._empty = build_empty_state(
            "Gelir Tablosu",
            "Seçtiğiniz dönemde satış, maliyet ve giderlerden kâr/zararın nasıl oluştuğunu gösterir.",
            cta_hint="Gelir Tablosu Getir",
        )
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return
        if self._bas.date() > self._bit.date():
            QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
            return

        bas = self._bas.date().toString("yyyy-MM-dd")
        bit = self._bit.date().toString("yyyy-MM-dd")
        self._btn_getir.setEnabled(False)
        self._status.setText("Dönem gelir/gider hareketleri çekiliyor…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            rows = fetch_gelir_tablosu(client, bas, bit)
            self._gt = build_gelir_tablosu(rows, bas=bas, bit=bit)
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Gelir tablosu getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        gt = self._gt
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_gelir_tablosu_widget(gt, firma=self._firma))
        self._btn_pdf.setEnabled(True)
        self._btn_csv.setEnabled(True)
        self._status.setText(f"{gt.hesap_sayisi} gelir/gider hesabı · Net Kâr {tl(gt.net_kar)} "
                             f"(net marj {yuzde(gt.net_marj)})")
        self._status.setStyleSheet(f"color: {OK};" if gt.net_kar >= 0 else f"color: {BAD};")

    def _on_pdf(self) -> None:
        if not self._gt:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Kaydet", f"gelir_tablosu_{self._gt.bas}_{self._gt.bit}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_gelir_tablosu_pdf(self._gt, path, firma=self._firma)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF Hatası", str(exc))
            return
        self._status.setText(f"PDF kaydedildi: {Path(path).name}")
        self._status.setStyleSheet(f"color: {OK};")

    def _on_csv(self) -> None:
        if not self._gt:
            return
        _csv_kaydet(self, self._status, f"gelir_tablosu_{self._gt.bas}_{self._gt.bit}.csv",
                    gelir_tablosu_csv(self._gt))


class GercekDurumTab(QWidget):
    """Fiili stok + banka hareketinden nakit & kârlılık üreten bağımsız rapor sekmesi."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._gd: GercekDurum | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        self._bas = TarihSecici(self._donem.bas_tarih(), genislik=130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = TarihSecici(self._donem.bit_tarih(), genislik=130)
        controls.addWidget(self._bit)
        _donem_aralik_bagla(self, self._donem, self._bas, self._bit)

        self._btn_ayarlar = QPushButton("Ayarlar")
        self._btn_ayarlar.setObjectName("ghostBtn")
        self._btn_ayarlar.clicked.connect(self._on_ayarlar)
        controls.addWidget(self._btn_ayarlar)

        self._btn_getir = QPushButton("Nakit && Kârlılık Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Nakit & Kârlılık Getir»e basın.")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        self._empty = build_empty_state(
            "Nakit & Kârlılık",
            "Faturalar muhasebeleştirilmeden, deponuzdan geçen mal ve bankadan geçen para üzerinden işletmenin fiili kârlılığını ve nakdini hesaplar.",
            cta_hint="Analizi Getir",
        )

        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _on_ayarlar(self) -> None:
        dlg = GercekDurumAyarlarDialog(self)
        if dlg.exec():
            a = dlg.ayarlar()
            self._status.setText(f"Ayarlar kaydedildi — {a.ozet()}")
            self._status.setStyleSheet(f"color: {OK};")


    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return
        if self._bas.date() > self._bit.date():
            QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
            return

        bas = self._bas.date().toString("yyyy-MM-dd")
        bit = self._bit.date().toString("yyyy-MM-dd")
        ayarlar = load_gercek_durum_ayarlar()
        self._btn_getir.setEnabled(False)
        self._status.setText("Stok, banka ve bakiye hareketleri çekiliyor…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            stok_rows = fetch_stok_ozet(client, bas, bit)
            stok_aylik = fetch_stok_aylik(client, bas, bit)
            nakit_rows = fetch_nakit_ozet(client, bas, bit)
            nakit_aylik = fetch_nakit_aylik(client, bas, bit)
            cari_bakiye_rows = fetch_cari_bakiye(client, bit)
            mizan_rows = fetch_mizan(client, bit)
            bilanco = build_bilanco(mizan_rows, asof=bit)
            # Resmi GL (karşılaştırma için) — başarısız olsa da rapor üretilir.
            try:
                gt = build_gelir_tablosu(fetch_gelir_tablosu(client, bas, bit), bas=bas, bit=bit)
            except MikroAPIError:
                gt = None
            self._gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                cari_bakiye_rows=cari_bakiye_rows,
                bilanco=bilanco, gelir_tablosu=gt,
                bas=bas, bit=bit, ayarlar=ayarlar,
            )
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Rapor getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        gd = self._gd
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_gercek_durum_widget(gd, firma=self._firma))
        self._btn_csv.setEnabled(True)
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
        self._status.setText(" · ".join(parts))
        self._status.setStyleSheet(
            f"color: {WARN};" if gd.veri_eksik else
            (f"color: {OK};" if gd.gercek_brut_kar >= 0 else f"color: {BAD};")
        )


    def _on_csv(self) -> None:
        if not self._gd:
            return
        _csv_kaydet(self, self._status, f"nakit_karlilik_{self._gd.bas}_{self._gd.bit}.csv",
                    gercek_durum_csv(self._gd))


class TahsilatAlacakTab(QWidget):
    """Cari hareketten alacak/borç yaşlandırma, vade takvimi ve tahsilat performansı sekmesi."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._ta: TahsilatAlacak | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        self._bas = TarihSecici(self._donem.bas_tarih(), genislik=130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = TarihSecici(self._donem.bit_tarih(), genislik=130)
        controls.addWidget(self._bit)
        _donem_aralik_bagla(self, self._donem, self._bas, self._bit)

        self._btn_getir = QPushButton("Tahsilat && Alacak Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Tahsilat & Alacak Getir»e basın.")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        self._empty = build_empty_state(
            "Tahsilat & Alacak",
            "Cari hareketlerden açık alacak ve borçların vadeye göre yaşlandırması, dönem tahsilat/ödeme performansı ve ileriye dönük net vade takvimi.",
            cta_hint="Analizi Getir",
        )

        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return
        if self._bas.date() > self._bit.date():
            QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
            return

        bas = self._bas.date().toString("yyyy-MM-dd")
        bit = self._bit.date().toString("yyyy-MM-dd")
        self._btn_getir.setEnabled(False)
        self._status.setText("Cari açık kalemler çekiliyor…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            vade_gun_map = fetch_cari_vade_gun(client)
            acik_rows = fetch_acik_kalemler(client, bit, bas, bit)
            self._ta = build_tahsilat_alacak(
                acik_rows, vade_gun_map=vade_gun_map, bas=bas, bit=bit)
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Tahsilat & alacak getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        ta = self._ta
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_tahsilat_alacak_widget(ta, firma=self._firma))
        self._btn_csv.setEnabled(True)
        parts = [
            f"{ta.cari_sayisi} cari hesap",
            f"Alacak {tl(ta.alacak_toplam)} (gecikmiş {tl(ta.alacak_gecikmis)})",
            f"Borç {tl(ta.borc_toplam)}",
        ]
        if ta.dso is not None:
            parts.append(f"DSO {ta.dso:.0f}g")
        if ta.cari_sayisi == 0:
            parts.insert(0, "⚠ açık bakiye yok — dönem/yıl kontrol edin")
        self._status.setText(" · ".join(parts))
        self._status.setStyleSheet(
            f"color: {WARN};" if ta.cari_sayisi == 0 else
            (f"color: {BAD};" if ta.alacak_gecikmis > 0.005 else f"color: {OK};")
        )


    def _on_csv(self) -> None:
        if not self._ta:
            return
        _csv_kaydet(self, self._status, f"tahsilat_alacak_{self._ta.bas}_{self._ta.bit}.csv",
                    tahsilat_alacak_csv(self._ta))


class NakitAkisTab(QWidget):
    """Banka/kasa hareketinden kategorize nakit akış (tahsilat, ödeme, kredi…) sekmesi."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._na: NakitAkis | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        self._bas = TarihSecici(self._donem.bas_tarih(), genislik=130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = TarihSecici(self._donem.bit_tarih(), genislik=130)
        controls.addWidget(self._bit)
        _donem_aralik_bagla(self, self._donem, self._bas, self._bit)

        self._btn_getir = QPushButton("Nakit Akışı Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Nakit Akışı Getir»e basın.")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        self._empty = build_empty_state(
            "Nakit Akış",
            "Banka ve kasadan fiilen geçen para — müşteri tahsilatı, satıcı ödemesi, kredi, vergi, personel; açılıştan kapanışa reconcile.",
            cta_hint="Nakit Akış Getir",
        )

        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _on_getir(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return
        if self._bas.date() > self._bit.date():
            QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
            return

        bas = self._bas.date().toString("yyyy-MM-dd")
        bit = self._bit.date().toString("yyyy-MM-dd")
        self._btn_getir.setEnabled(False)
        self._status.setText("Banka/kasa hareketleri çekiliyor…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            hareket_rows = fetch_nakit_akis_hareket(client, bas, bit)
            kapanis_rows = fetch_cari_bakiye(client, bit)
            donem_delta = fetch_nakit_delta(client, bas, bit)
            self._na = build_nakit_akis(
                hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                donem_delta=donem_delta, bas=bas, bit=bit)
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)
            self._status.setText("Nakit akış getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_getir.setEnabled(True)

        na = self._na
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_nakit_akis_widget(na, firma=self._firma))
        self._btn_csv.setEnabled(True)
        parts = [
            f"Giriş {tl(na.toplam_giris)}",
            f"Çıkış {tl(na.toplam_cikis)}",
            f"Net {tl(na.net_akis)}",
        ]
        if na.kredi_odeme > 0.005 or na.kredi_kullanim > 0.005:
            parts.append(f"Kredi net {tl(na.kredi_net)}")
        if na.hareket_sayisi == 0:
            parts.insert(0, "⚠ banka/kasa hareketi yok — dönem/yıl kontrol edin")
        self._status.setText(" · ".join(parts))
        self._status.setStyleSheet(
            f"color: {WARN};" if na.hareket_sayisi == 0 else
            (f"color: {OK};" if na.net_akis >= 0 else f"color: {BAD};")
        )


    def _on_csv(self) -> None:
        if not self._na:
            return
        _csv_kaydet(self, self._status, f"nakit_akis_{self._na.bas}_{self._na.bit}.csv",
                    nakit_akis_csv(self._na))


def _para_spin(maks: float = 1e12) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(-maks, maks)
    sp.setDecimals(0)
    sp.setSingleStep(10000)
    sp.setGroupSeparatorShown(True)
    sp.setSuffix(" TL")
    sp.setMinimumWidth(150)
    return sp


def _yuzde_spin(alt: float, ust: float) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(alt, ust)
    sp.setDecimals(1)
    sp.setSingleStep(0.5)
    sp.setSuffix(" %")
    sp.setMinimumWidth(90)
    return sp


class TahminTab(QWidget):
    """Geçmiş trendden otomatik önerip kullanıcının düzenlediği ileriye dönük projeksiyon."""

    def __init__(self, donem: DonemDurumu, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._donem = donem
        self._t: Tahmin | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        bar = QFrame()
        bar.setObjectName("tabToolbar")
        controls = QHBoxLayout(bar)
        controls.setContentsMargins(14, 10, 14, 10)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Geçmiş veri dönemi:"))
        self._bas = TarihSecici(self._donem.bas_tarih(), genislik=120)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = TarihSecici(self._donem.bit_tarih(), genislik=120)
        controls.addWidget(self._bit)
        _donem_aralik_bagla(self, self._donem, self._bas, self._bit)
        self._btn_doldur = QPushButton("Geçmişten Doldur")
        self._btn_doldur.setObjectName("primaryBtn")
        self._btn_doldur.clicked.connect(self._on_doldur)
        controls.addWidget(self._btn_doldur)
        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setObjectName("ghostBtn")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)
        self._status = QLabel("«Geçmişten Doldur» ile başla; sonra varsayımları düzenle.")
        self._status.setStyleSheet(f"color: {MUTED};")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addWidget(bar)

        # Varsayım formu (senaryo) — düzenlenebilir
        form_box = QFrame()
        form_box.setObjectName("tahminForm")
        form_box.setStyleSheet(
            "QFrame#tahminForm { background: #f7f9fc; border: 1px solid #e2e6ec; border-radius: 12px; }")
        fl = QHBoxLayout(form_box)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(18)
        self._sp_nakit = _para_spin()
        self._sp_ciro = _para_spin()
        self._sp_gider = _para_spin()
        self._sp_buyume = _yuzde_spin(-50.0, 100.0)
        self._sp_marj = _yuzde_spin(0.0, 100.0)
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
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            col.addRow(lbl, w)
            fl.addLayout(col)
        self._btn_projekte = QPushButton("Projekte Et")
        self._btn_projekte.setObjectName("primaryBtn")
        self._btn_projekte.clicked.connect(self._on_projekte)
        fl.addWidget(self._btn_projekte)
        layout.addWidget(form_box)

        self._empty = build_empty_state(
            "Tahmin",
            "Geçmiş trendden otomatik tahmin üretir; varsayımları (büyüme, marj, gider) düzenleyip senaryonu görebilirsiniz.",
            cta_hint="Geçmişten Doldur",
        )
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _on_doldur(self) -> None:
        cfg = load_config()
        if not cfg.is_complete():
            cevap = QMessageBox.question(
                self, "Mikro Ayarları Eksik",
                "Mikro bağlantı bilgileri eksik. Üstteki «Mikro Ayarları»'ndan doldurun.\n\n"
                "Şimdi açmak ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if cevap == QMessageBox.StandardButton.Yes:
                MikroAyarlarDialog(self).exec()
            return
        if self._bas.date() > self._bit.date():
            QMessageBox.warning(self, "Tarih Hatası", "Başlangıç tarihi bitişten sonra olamaz.")
            return

        bas = self._bas.date().toString("yyyy-MM-dd")
        bit = self._bit.date().toString("yyyy-MM-dd")
        self._btn_doldur.setEnabled(False)
        self._status.setText("Geçmiş veri çekiliyor (satış, marj, nakit, gider)…")
        self._status.setStyleSheet(f"color: {MUTED};")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            stok_rows = fetch_stok_ozet(client, bas, bit)
            stok_aylik = fetch_stok_aylik(client, bas, bit)
            gd = build_gercek_durum(stok_rows=stok_rows, stok_aylik=stok_aylik, bas=bas, bit=bit)
            kapanis_rows = fetch_cari_bakiye(client, bit)
            baslangic_nakit = _nakit_bakiye(kapanis_rows)
            hareket_rows = fetch_nakit_akis_hareket(client, bas, bit)
            donem_delta = fetch_nakit_delta(client, bas, bit)
            na = build_nakit_akis(hareket_rows, bakiye_kapanis_rows=kapanis_rows,
                                  donem_delta=donem_delta, bas=bas, bit=bit)
            firma = (cfg.firma_adi or "").strip()
            if not firma:
                try:
                    firma = fetch_firma_adi(client)
                except MikroAPIError:
                    firma = ""
            self._firma = firma
        except MikroAPIError as exc:
            QApplication.restoreOverrideCursor()
            self._btn_doldur.setEnabled(True)
            self._status.setText("Geçmiş veri getirilemedi.")
            self._status.setStyleSheet(f"color: {BAD};")
            QMessageBox.warning(self, "Mikro Hatası", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._btn_doldur.setEnabled(True)

        satis_serisi = [a.satis for a in gd.trend]
        ay_sayisi = max(1, len(na.aylik))
        sabit_gider = (na.toplam_cikis
                       - na.cikis_kategori.get("Satıcı ödemesi", 0.0)
                       - na.kredi_odeme) / ay_sayisi
        v = oner_varsayim(
            satis_serisi=satis_serisi, brut_marj_yuzde=gd.gercek_brut_marj,
            baslangic_nakit=baslangic_nakit, aylik_sabit_gider=sabit_gider,
            baslangic_ay=bit[:7], ufuk_ay=self._sp_ufuk.value(),
        )
        self._sp_nakit.setValue(v.baslangic_nakit)
        self._sp_ciro.setValue(v.baz_ciro)
        self._sp_buyume.setValue(v.buyume_yuzde)
        self._sp_marj.setValue(v.marj_yuzde)
        self._sp_gider.setValue(v.sabit_gider)
        self._status.setText("Geçmişten dolduruldu — varsayımları düzenleyip «Projekte Et»e basabilirsin.")
        self._status.setStyleSheet(f"color: {OK};")
        self._on_projekte()


    def _on_projekte(self) -> None:
        v = TahminVarsayim(
            baslangic_ay=self._bit.date().toString("yyyy-MM"),
            baslangic_nakit=self._sp_nakit.value(),
            baz_ciro=self._sp_ciro.value(),
            buyume_yuzde=self._sp_buyume.value(),
            marj_yuzde=self._sp_marj.value(),
            sabit_gider=self._sp_gider.value(),
            ufuk_ay=self._sp_ufuk.value(),
        )
        self._t = build_tahmin(v)
        self._empty.setVisible(False)
        self._view.setVisible(True)
        self._view.setWidget(build_tahmin_widget(self._t, firma=self._firma))
        self._btn_csv.setEnabled(True)
        self._status.setText(
            f"Tahmin: {self._sp_ufuk.value()} ay · toplam ciro {tl(self._t.toplam_ciro)} · "
            f"dönem sonu nakit {tl(self._t.son_nakit)}")
        self._status.setStyleSheet(
            f"color: {BAD};" if self._t.en_dusuk_nakit < 0 else f"color: {OK};")

    def _on_csv(self) -> None:
        if not self._t:
            return
        _csv_kaydet(self, self._status, f"tahmin_{self._t.varsayim.baslangic_ay}.csv",
                    tahmin_csv(self._t))


# ---------------------------------------------------------------------------
# Ana pencere
# ---------------------------------------------------------------------------

class MikRaporWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MikRapor — Finansal Raporlama")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1080, 720)
        self.resize(1220, 840)
        self._donem = DonemDurumu()
        self._build()

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("rootArea")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Üst marka bar (Teal A)
        brand_bar = QFrame()
        brand_bar.setObjectName("brandBar")
        header = QHBoxLayout(brand_bar)
        header.setContentsMargins(4, 2, 4, 8)
        header.setSpacing(12)
        logo = QLabel()
        pm = app_logo_pixmap(48)
        if not pm.isNull():
            logo.setPixmap(pm)
            logo.setFixedSize(48, 48)
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.setContentsMargins(0, 0, 0, 0)
        baslik = QLabel("MikRapor")
        baslik.setObjectName("titleLabel")
        titles.addWidget(baslik)
        alt = QLabel("Mikro finansal raporlar")
        alt.setObjectName("brandSubtitle")
        titles.addWidget(alt)
        header.addLayout(titles)
        header.addStretch()
        self._conn = QLabel()
        self._conn.setObjectName("connStatus")
        header.addWidget(self._conn)
        btn_ayar = QPushButton("Mikro Ayarları")
        btn_ayar.setObjectName("ghostBtn")
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar)
        layout.addWidget(brand_bar)
        self._refresh_conn_status()

        # Sekmeler — her rapor kendi sekmesinde (ortak dönem)
        self._tabs = QTabWidget()
        self._tabs.addTab(BilancoTab(self._donem), "Anında Bilanço")
        self._tabs.addTab(GelirTablosuTab(self._donem), "Gelir Tablosu")
        self._tabs.addTab(GercekDurumTab(self._donem), "Nakit && Kârlılık")
        self._tabs.addTab(TahsilatAlacakTab(self._donem), "Tahsilat && Alacak")
        self._tabs.addTab(NakitAkisTab(self._donem), "Nakit Akış")
        self._tabs.addTab(TahminTab(self._donem), "Tahmin")
        layout.addWidget(self._tabs, stretch=1)

    def _refresh_conn_status(self) -> None:
        cfg = load_config()
        if cfg.is_complete():
            kod = cfg.firma_kodu or "—"
            ad = (cfg.firma_adi or "").strip()
            label = f"Bağlı · Firma {kod}" + (f" · {ad[:28]}" if ad else "")
            self._conn.setText(label)
            self._conn.setProperty("connected", True)
        else:
            self._conn.setText("Bağlantı ayarlanmadı")
            self._conn.setProperty("connected", False)
        # property değişince QSS yenilensin
        self._conn.style().unpolish(self._conn)
        self._conn.style().polish(self._conn)

    def _on_ayarlar(self) -> None:
        if MikroAyarlarDialog(self).exec():
            self._refresh_conn_status()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(app_icon())
    if _try_activate_existing_instance():
        return 0
    window = MikRaporWindow()
    server = _start_single_instance_server(window)
    del server
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
