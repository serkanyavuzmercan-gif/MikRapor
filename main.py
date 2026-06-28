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

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from gercek_durum_view import build_gercek_durum_widget
from mikro_api import MikroAPIError, MikroClient
from mikro_fetch import (
    fetch_bakiye_ozet,
    fetch_firma_adi,
    fetch_gelir_tablosu,
    fetch_mizan,
    fetch_nakit_aylik,
    fetch_nakit_ozet,
    fetch_stok_aylik,
    fetch_stok_ozet,
)
from mikro_settings_dialog import MikroAyarlarDialog
from mizan_bilanco import Bilanco, bilanco_csv, build_bilanco, tl
from resources import app_icon, app_logo_pixmap
from styles import DARK_STYLESHEET

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
# Anında Bilanço sekmesi
# ---------------------------------------------------------------------------

class BilancoTab(QWidget):
    """Tarih itibarıyla bilanço üreten bağımsız rapor sekmesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bilanco: Bilanco | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Tarih itibarıyla:"))
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd.MM.yyyy")
        self._date.setDate(QDate.currentDate())
        self._date.setFixedWidth(140)
        controls.addWidget(self._date)

        self._btn_getir = QPushButton("Bilanço Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_pdf = QPushButton("PDF Kaydet")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_pdf)
        controls.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Tarih seçip «Bilanço Getir»e basın.")
        self._status.setStyleSheet("color: #8b929e;")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addLayout(controls)

        self._empty = self._build_empty()
        layout.addWidget(self._empty, stretch=1)
        # Bilanço gövdesi yerel widget'larla (QTreeWidget) çizilir; satır :hover vurgusu
        # için zengin-metin yerine yerel görünüm. Dış scroll tüm sayfayı birlikte kaydırır.
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: #f4f6f9; border: none; }")
        self._view.setVisible(False)
        layout.addWidget(self._view, stretch=1)

    def _build_empty(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch()
        lbl = QLabel(
            "<div align='center' style='font-family:Segoe UI;'>"
            "<div style='font-size:46px;'>📊</div>"
            "<div style='font-size:22px; font-weight:800; color:#374151; margin-top:6px;'>Anında Bilanço</div>"
            "<div style='color:#6b7280; margin-top:12px; line-height:160%;'>"
            "Mikro genel muhasebe verinizden, seçtiğiniz tarih itibarıyla<br>"
            "bilançoyu saniyeler içinde üretir.</div>"
            "<div style='color:#94a3b8; margin-top:16px; font-size:12px;'>"
            "Tarihi seçin&nbsp; →&nbsp; <b style='color:#2f6fed;'>Bilanço Getir</b>'e basın</div>"
            "</div>"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

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
        self._status.setStyleSheet("color: #8b929e;")
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
            self._status.setStyleSheet("color: #e57373;")
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
            self._status.setStyleSheet("color: #81c784;")
        elif b.dengede:
            self._status.setText(f"{len(rows)} hesap · ≈ dengede (kalan %{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet("color: #ffb74d;")
        else:
            self._status.setText(f"{len(rows)} hesap · FARK var (%{b.denge_yuzde:.2f}).")
            self._status.setStyleSheet("color: #e57373;")

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
        self._status.setStyleSheet("color: #81c784;")

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
    status.setStyleSheet("color: #81c784;")


def _hos_geldin(emoji: str, baslik: str, aciklama: str) -> QWidget:
    """Sekme boşken gösterilen ortalanmış karşılama widget'ı."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addStretch()
    lbl = QLabel(
        f"<div align='center' style='font-family:Segoe UI;'>"
        f"<div style='font-size:46px;'>{emoji}</div>"
        f"<div style='font-size:22px; font-weight:800; color:#374151; margin-top:6px;'>{baslik}</div>"
        f"<div style='color:#6b7280; margin-top:12px; line-height:160%;'>{aciklama}</div>"
        f"<div style='color:#94a3b8; margin-top:16px; font-size:12px;'>"
        f"Dönemi seçin&nbsp; →&nbsp; <b style='color:#2f6fed;'>Getir</b>'e basın</div>"
        f"</div>"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    lay.addStretch()
    return w


class GelirTablosuTab(QWidget):
    """Dönem (başlangıç–bitiş) gelir tablosu üreten bağımsız rapor sekmesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gt: GelirTablosu | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        yil = load_config().calisma_yili or QDate.currentDate().year()
        self._bas = QDateEdit()
        self._bas.setCalendarPopup(True)
        self._bas.setDisplayFormat("dd.MM.yyyy")
        self._bas.setDate(QDate(yil, 1, 1))
        self._bas.setFixedWidth(130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = QDateEdit()
        self._bit.setCalendarPopup(True)
        self._bit.setDisplayFormat("dd.MM.yyyy")
        self._bit.setDate(QDate.currentDate())
        self._bit.setFixedWidth(130)
        controls.addWidget(self._bit)

        self._btn_getir = QPushButton("Gelir Tablosu Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)
        self._btn_pdf = QPushButton("PDF Kaydet")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_pdf)
        controls.addWidget(self._btn_pdf)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Gelir Tablosu Getir»e basın.")
        self._status.setStyleSheet("color: #8b929e;")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addLayout(controls)

        self._empty = _hos_geldin("📈", "Gelir Tablosu",
                                  "Seçtiğiniz dönemde satış, maliyet ve giderlerden<br>"
                                  "kâr/zararın nasıl oluştuğunu gösterir.")
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: #f4f6f9; border: none; }")
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
        self._status.setStyleSheet("color: #8b929e;")
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
            self._status.setStyleSheet("color: #e57373;")
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
        self._status.setStyleSheet("color: #81c784;" if gt.net_kar >= 0 else "color: #e57373;")

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
        self._status.setStyleSheet("color: #81c784;")

    def _on_csv(self) -> None:
        if not self._gt:
            return
        _csv_kaydet(self, self._status, f"gelir_tablosu_{self._gt.bas}_{self._gt.bit}.csv",
                    gelir_tablosu_csv(self._gt))


class GercekDurumTab(QWidget):
    """Operasyonel gerçeği (stok+banka) doğrudan Mikro'dan üreten bağımsız rapor sekmesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gd: GercekDurum | None = None
        self._firma: str = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Dönem:"))
        yil = load_config().calisma_yili or QDate.currentDate().year()
        self._bas = QDateEdit()
        self._bas.setCalendarPopup(True)
        self._bas.setDisplayFormat("dd.MM.yyyy")
        self._bas.setDate(QDate(yil, 1, 1))
        self._bas.setFixedWidth(130)
        controls.addWidget(self._bas)
        controls.addWidget(QLabel("→"))
        self._bit = QDateEdit()
        self._bit.setCalendarPopup(True)
        self._bit.setDisplayFormat("dd.MM.yyyy")
        self._bit.setDate(QDate.currentDate())
        self._bit.setFixedWidth(130)
        controls.addWidget(self._bit)

        controls.addWidget(QLabel("Satış bazı:"))
        self._baz = QComboBox()
        self._baz.addItem("İrsaliye + Fatura", "sevk")
        self._baz.addItem("Yalnız Fatura", "fatura")
        self._baz.setFixedWidth(150)
        controls.addWidget(self._baz)

        self._btn_getir = QPushButton("Gerçek Durumu Getir")
        self._btn_getir.setObjectName("primaryBtn")
        self._btn_getir.clicked.connect(self._on_getir)
        controls.addWidget(self._btn_getir)

        self._btn_csv = QPushButton("CSV Kaydet")
        self._btn_csv.setEnabled(False)
        self._btn_csv.clicked.connect(self._on_csv)
        controls.addWidget(self._btn_csv)

        self._status = QLabel("Dönem seçip «Gerçek Durumu Getir»e basın.")
        self._status.setStyleSheet("color: #8b929e;")
        self._status.setWordWrap(True)
        controls.addWidget(self._status, stretch=1)
        layout.addLayout(controls)

        self._empty = _hos_geldin(
            "🛰️", "Gerçek Durum",
            "Doğrudan Mikro'dan, fiili stok ve banka hareketine dayanarak<br>"
            "gerçek brüt marjı, nakit akışını ve resmi tabloyla farkı gösterir.")
        layout.addWidget(self._empty, stretch=1)
        self._view = QScrollArea()
        self._view.setWidgetResizable(True)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setStyleSheet("QScrollArea { background: #f4f6f9; border: none; }")
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
        satis_bazi = self._baz.currentData() or "sevk"
        self._btn_getir.setEnabled(False)
        self._status.setText("Stok, banka ve bakiye hareketleri çekiliyor…")
        self._status.setStyleSheet("color: #8b929e;")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        client = MikroClient(cfg)
        try:
            stok_rows = fetch_stok_ozet(client, bas, bit)
            stok_aylik = fetch_stok_aylik(client, bas, bit)
            nakit_rows = fetch_nakit_ozet(client, bas, bit)
            nakit_aylik = fetch_nakit_aylik(client, bas, bit)
            bakiye_rows = fetch_bakiye_ozet(client, bit)
            # Resmi GL (karşılaştırma için) — başarısız olsa da gerçek durum üretilir.
            try:
                gt = build_gelir_tablosu(fetch_gelir_tablosu(client, bas, bit), bas=bas, bit=bit)
            except MikroAPIError:
                gt = None
            self._gd = build_gercek_durum(
                stok_rows=stok_rows, stok_aylik=stok_aylik,
                nakit_rows=nakit_rows, nakit_aylik=nakit_aylik,
                bakiye_rows=bakiye_rows, gelir_tablosu=gt,
                bas=bas, bit=bit, satis_bazi=satis_bazi,
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
            self._status.setText("Gerçek durum getirilemedi.")
            self._status.setStyleSheet("color: #e57373;")
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
        self._status.setText(
            f"Gerçek brüt marj {yuzde(gd.gercek_brut_marj)} · Net nakit {tl(gd.nakit_net)}")
        self._status.setStyleSheet("color: #81c784;" if gd.gercek_brut_kar >= 0 else "color: #e57373;")

    def _on_csv(self) -> None:
        if not self._gd:
            return
        _csv_kaydet(self, self._status, f"gercek_durum_{self._gd.bas}_{self._gd.bit}.csv",
                    gercek_durum_csv(self._gd))


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
        self._build()

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("rootArea")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Üst bar: logo + MikRapor + global Mikro Ayarları
        header = QHBoxLayout()
        logo = QLabel()
        pm = app_logo_pixmap(40)
        if not pm.isNull():
            logo.setPixmap(pm)
            logo.setFixedSize(40, 40)
        header.addWidget(logo)
        baslik = QLabel("MikRapor")
        baslik.setObjectName("titleLabel")
        header.addWidget(baslik)
        alt = QLabel("Finansal Raporlama")
        alt.setStyleSheet("color: #8b929e; font-size: 12px; margin-left: 4px;")
        header.addWidget(alt)
        header.addStretch()
        btn_ayar = QPushButton("Mikro Ayarları")
        btn_ayar.clicked.connect(self._on_ayarlar)
        header.addWidget(btn_ayar)
        layout.addLayout(header)

        # Sekmeler — her rapor kendi sekmesinde
        self._tabs = QTabWidget()
        self._tabs.addTab(BilancoTab(), "Anında Bilanço")
        self._tabs.addTab(GelirTablosuTab(), "Gelir Tablosu")
        self._tabs.addTab(GercekDurumTab(), "Gerçek Durum")
        layout.addWidget(self._tabs, stretch=1)

    def _on_ayarlar(self) -> None:
        MikroAyarlarDialog(self).exec()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
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
