#!/usr/bin/env python3
"""
MikRapor — Finansal analiz ve nakit akışı (PyQt6).
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analyzer import MonthlyAnalysisReport, format_tl, run_monthly_analysis
from bank_parser import BankParseError, load_banka_dosyalari
from cari_plan_parser import CariPlanParseError, load_tahsilat_plan, load_tediye_plan
from charts import build_all_charts, chart_display_info
from exporter import export_excel, export_pdf, export_text, export_word
from fatura_parser import (
    FaturaParseError,
    load_alis_faturalari_dosyalari,
    load_satis_faturalari_dosyalari,
)
from models import AnalizVeriSeti, AylikMaasGirisi
from muavin_parser import MuavinParseError, load_muavin, validate_muavin_month_range
from operational_analyzer import PersonelMaas
from metric_labels import metric_kaynak, metric_short, metric_title
from parse_utils import MizanParseError
from period_utils import analiz_ayi_label, filter_df_by_analiz_ayi, recent_analiz_aylari
from resources import app_icon, app_logo_pixmap
from styles import DARK_STYLESHEET

INSTANCE_KEY = "MercanSoftware.MikRapor.SingleInstance"


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


def _bring_window_to_front(window: QMainWindow) -> None:
    if window.isMinimized():
        window.showNormal()
    window.show()
    window.raise_()
    window.activateWindow()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(int(window.winId()))
        except Exception:
            pass


def _on_secondary_launch(server: QLocalServer, window: QMainWindow) -> None:
    connection = server.nextPendingConnection()
    if connection is None:
        return
    connection.waitForReadyRead(300)
    connection.readAll()
    connection.disconnectFromServer()
    _bring_window_to_front(window)


def _start_single_instance_server(window: QMainWindow) -> QLocalServer:
    QLocalServer.removeServer(INSTANCE_KEY)
    server = QLocalServer()
    if not server.listen(INSTANCE_KEY):
        raise RuntimeError("Tek örnek sunucusu başlatılamadı.")
    server.newConnection.connect(lambda: _on_secondary_launch(server, window))
    return server


class MikRaporWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MikRapor — Finansal Analiz ve Nakit Akışı")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1100, 720)
        self.resize(1200, 800)

        self._muavin_df: pd.DataFrame = pd.DataFrame()
        self._alis_fatura_df: pd.DataFrame = pd.DataFrame()
        self._satis_fatura_df: pd.DataFrame = pd.DataFrame()
        self._banka_df: pd.DataFrame = pd.DataFrame()
        self._tahsilat_plan_df: pd.DataFrame = pd.DataFrame()
        self._tediye_plan_df: pd.DataFrame = pd.DataFrame()
        self._muavin_paths: list[str] = []
        self._alis_paths: list[str] = []
        self._satis_paths: list[str] = []
        self._banka_paths: list[str] = []
        self._tahsilat_plan_path = ""
        self._tediye_plan_path = ""
        self._report: MonthlyAnalysisReport | None = None
        self._charts: dict = {}
        self._dukkan_metrekare = 0.0
        self._maas_table_updating = False
        self._dirty = False
        self._last_analiz_label = ""

        self._build_ui()
        self._show_analysis_placeholder()
        self._update_status_label()

    def _selected_analiz_ayi(self) -> str:
        return self._analiz_ay_combo.currentData() or self._analiz_ay_combo.currentText()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 12)

        header_row = QHBoxLayout()
        logo_label = QLabel()
        logo_pm = app_logo_pixmap(44)
        if not logo_pm.isNull():
            logo_label.setPixmap(logo_pm)
            logo_label.setFixedSize(44, 44)
        header_row.addWidget(logo_label)

        title = QLabel("MikRapor — Finansal Analiz ve Nakit Akışı")
        title.setObjectName("titleLabel")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        ay_row = QHBoxLayout()
        ay_row.addWidget(QLabel("Analiz Ayı:"))
        self._analiz_ay_combo = QComboBox()
        for ay in recent_analiz_aylari(24):
            self._analiz_ay_combo.addItem(analiz_ayi_label(ay), ay)
        self._analiz_ay_combo.currentIndexChanged.connect(self._on_analiz_ayi_changed)
        ay_row.addWidget(self._analiz_ay_combo)

        self._btn_analiz = QPushButton("Analiz Et")
        self._btn_analiz.setObjectName("primaryBtn")
        self._btn_analiz.clicked.connect(self._run_analysis)
        ay_row.addWidget(self._btn_analiz)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        ay_row.addWidget(self._status_label, stretch=1)
        layout.addLayout(ay_row)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        self._tabs.addTab(self._build_load_tab(), "Veri Yükleme")
        self._tabs.addTab(self._build_analysis_tab(), "Analiz Özeti")
        self._tabs.addTab(self._build_charts_tab(), "Grafikler")
        self._tabs.addTab(self._build_report_tab(), "Rapor")

    def _build_load_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        def add_load_row(btn_text: str, handler, label_attr: str) -> None:
            row = QHBoxLayout()
            btn = QPushButton(btn_text)
            if "Muavin" in btn_text:
                btn.setObjectName("primaryBtn")
            btn.clicked.connect(handler)
            row.addWidget(btn)
            lbl = QLabel("Yüklenmedi.")
            lbl.setStyleSheet("color: #9aa0a8;")
            setattr(self, label_attr, lbl)
            row.addWidget(lbl, stretch=1)
            layout.addLayout(row)

        add_load_row("Muavin Defteri (.xlsx / .csv)", self._on_load_muavin, "_lbl_muavin")
        add_load_row("Alış Faturaları (.xlsx, çoklu)", self._on_load_alis, "_lbl_alis")
        add_load_row("Satış Faturaları (.xlsx, çoklu)", self._on_load_satis, "_lbl_satis")
        add_load_row("Banka Ekstreleri (.xlsx, çoklu)", self._on_load_banka, "_lbl_banka")
        add_load_row("120 Tahsilat Planı (.xlsx)", self._on_load_tahsilat_plan, "_lbl_tahsilat_plan")
        add_load_row("320 Ödeme Planı / Tediye (.xlsx)", self._on_load_tediye_plan, "_lbl_tediye_plan")

        param_row = QHBoxLayout()
        self._metrekare_spin = QDoubleSpinBox()
        self._metrekare_spin.setRange(0, 100000)
        self._metrekare_spin.setSuffix(" m²")
        self._metrekare_spin.valueChanged.connect(self._on_metrekare_changed)
        param_row.addWidget(QLabel("Dükkan m²:"))
        param_row.addWidget(self._metrekare_spin)
        param_row.addStretch()
        layout.addLayout(param_row)

        maas_group = QGroupBox("Manuel Maaş Girişi (Seçilen Ay)")
        maas_layout = QVBoxLayout(maas_group)
        self._maas_table = QTableWidget(0, 4)
        self._maas_table.setHorizontalHeaderLabels(["Ad", "Resmi Maaş", "Harici Maaş", "Toplam"])
        self._maas_table.horizontalHeader().setStretchLastSection(True)
        self._maas_table.cellChanged.connect(self._on_maas_cell_changed)
        maas_layout.addWidget(self._maas_table)
        btn_row = QHBoxLayout()
        btn_add = QPushButton("Satır Ekle")
        btn_add.clicked.connect(self._on_add_maas_row)
        btn_del = QPushButton("Satır Sil")
        btn_del.clicked.connect(self._on_del_maas_row)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        maas_layout.addLayout(btn_row)
        layout.addWidget(maas_group)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Önizleme:"))
        self._preview_combo = QComboBox()
        self._preview_combo.addItems([
            "Muavin", "Alış Faturaları", "Satış Faturaları", "Banka",
            "120 Tahsilat", "320 Tediye",
        ])
        self._preview_combo.currentIndexChanged.connect(self._apply_table_filter)
        filter_row.addWidget(self._preview_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)
        return tab

    def _build_analysis_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)

        self._cfo_banner = QLabel("")
        self._cfo_banner.setWordWrap(True)
        self._cfo_banner.setStyleSheet(
            "background-color: #1e3a5f; color: #e8eaed; padding: 12px; border-radius: 6px;"
        )
        layout.addWidget(self._cfo_banner)

        self._context_label = QLabel("Veri yüklenmedi.")
        self._context_label.setObjectName("contextLabel")
        layout.addWidget(self._context_label)

        self._ay_warning_label = QLabel("")
        self._ay_warning_label.setWordWrap(True)
        self._ay_warning_label.setVisible(False)
        self._ay_warning_label.setStyleSheet(
            "background-color: #5d4037; color: #ffe0b2; padding: 8px; border-radius: 4px;"
        )
        layout.addWidget(self._ay_warning_label)

        self._kpi_host = QWidget()
        self._kpi_grid = QGridLayout(self._kpi_host)
        layout.addWidget(self._kpi_host)

        self._nakit_table = self._make_table(["Kalem", "Tutar"])
        layout.addWidget(self._section_metric("Nakit Akış Özeti", "nakit_akis", self._nakit_table))

        self._pl_table = self._make_table(["Kalem", "Tutar"])
        layout.addWidget(self._section_metric("Aylık Kâr/Zarar", "aylik_net_kar", self._pl_table))

        self._karsilastirma_table = self._make_table(["Metrik", "Bu Ay", "Önceki Ay", "Fark"])
        layout.addWidget(self._section("Önceki Aya Göre", self._karsilastirma_table))

        self._mutabakat_table = self._make_table(["Kaynak", "Plan", "Yaşlandırma", "Fark"])
        layout.addWidget(self._section("Plan Mutabakatı", self._mutabakat_table))

        self._plan_table = self._make_table(
            ["Plan", "Açık Bakiye", "Vadesi Geçen", "Vadesi Gelmeyen", "Cari Sayısı"]
        )
        layout.addWidget(self._section_metric("Tahsilat ve Ödeme Planı", "vade_net", self._plan_table))

        self._plan_cari_table = self._make_table(
            ["Cari Kodu", "Cari Adı", "Açık", "Vadesi Geçen", "Vadesi Gelmeyen"]
        )
        layout.addWidget(self._section("Plan — En Yüksek Cariler", self._plan_cari_table))

        self._tahsil_table = self._make_table(
            ["Cari Kodu", "Fatura", "Banka Tahsilat", "Kalan", "Bucket"]
        )
        layout.addWidget(self._section_metric("Tahsil Edilemeyen Satışlar", "tahsil_edilemeyen", self._tahsil_table))

        self._odeme_table = self._make_table(
            ["Cari Kodu", "Fatura", "Banka Ödeme", "Kalan", "Bucket"]
        )
        layout.addWidget(self._section_metric("Ödenmeyen Faturalar", "odenmeyen", self._odeme_table))

        self._acik_table = self._make_table(
            ["Tarih", "Banka", "Karşı Hesap", "Açıklama", "Tutar"]
        )
        layout.addWidget(self._section("Kayıt Dışı Giderler", self._acik_table))

        self._kar_table = self._make_table(["Stok", "Marj %", "Brüt Kâr"])
        layout.addWidget(self._section("Yüksek Marjlı Satışlar", self._kar_table))

        self._recommendations_text = QTextEdit()
        self._recommendations_text.setReadOnly(True)
        layout.addWidget(self._section("Tavsiyeler", self._recommendations_text))

        scroll.setWidget(container)
        return scroll

    def _build_charts_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._charts_layout = QVBoxLayout(container)
        placeholder = QLabel("Analiz çalıştırıldığında grafikler burada görünür.")
        placeholder.setStyleSheet("color: #9aa0a8;")
        self._charts_layout.addWidget(placeholder)
        scroll.setWidget(container)
        return scroll

    def _build_report_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        export_row = QHBoxLayout()
        for label, handler in [
            ("PDF", self._export_pdf),
            ("Excel", self._export_excel),
            ("Word", self._export_word),
            ("Metin", self._export_text),
        ]:
            btn = QPushButton(f"{label} Dışa Aktar")
            btn.clicked.connect(handler)
            export_row.addWidget(btn)
        export_row.addStretch()
        layout.addLayout(export_row)

        self._report_preview = QTextEdit()
        self._report_preview.setReadOnly(True)
        layout.addWidget(self._report_preview)
        return tab

    def _section(self, title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.addWidget(widget)
        return box

    def _section_metric(self, fallback_title: str, metric_key: str, widget: QWidget) -> QGroupBox:
        title = metric_title(metric_key) if metric_key else fallback_title
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        if metric_key:
            hint = QLabel(metric_kaynak(metric_key))
            hint.setStyleSheet("color: #9aa0a8; font-size: 10px;")
            hint.setWordWrap(True)
            lay.addWidget(hint)
        lay.addWidget(widget)
        return box

    def _make_table(self, headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _on_analiz_ayi_changed(self) -> None:
        self._mark_dirty()
        self._update_ay_warning(self._selected_analiz_ayi())
        self._update_status_label()

    def _has_loaded_data(self) -> bool:
        return bool(
            not self._muavin_df.empty
            or not self._alis_fatura_df.empty
            or not self._satis_fatura_df.empty
            or not self._banka_df.empty
            or not self._tahsilat_plan_df.empty
            or not self._tediye_plan_df.empty
        )

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._report = None
        self._update_status_label()

    def _update_status_label(self) -> None:
        if not self._has_loaded_data():
            self._status_label.setText("Veri yükleyin.")
            self._status_label.setStyleSheet("color: #9aa0a8;")
            self._btn_analiz.setEnabled(False)
            return
        self._btn_analiz.setEnabled(True)
        if self._dirty or not self._report:
            self._status_label.setText("Veri hazır — analiz bekleniyor.")
            self._status_label.setStyleSheet("color: #ffb74d;")
        else:
            label = self._last_analiz_label or analiz_ayi_label(self._selected_analiz_ayi())
            self._status_label.setText(f"Son analiz: {label}")
            self._status_label.setStyleSheet("color: #81c784;")

    def _show_analysis_placeholder(self) -> None:
        msg = "Analiz için üstteki «Analiz Et» butonuna basın."
        self._cfo_banner.setText(msg)
        self._context_label.setText(msg)
        self._clear_layout(self._kpi_grid)
        for table in (
            self._nakit_table, self._pl_table, self._karsilastirma_table, self._mutabakat_table,
            self._plan_table, self._plan_cari_table,
            self._tahsil_table, self._odeme_table, self._acik_table, self._kar_table,
        ):
            table.setRowCount(0)
        self._recommendations_text.setPlainText(msg)
        self._report_preview.setPlainText(msg)
        while self._charts_layout.count():
            item = self._charts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        placeholder = QLabel(msg)
        placeholder.setStyleSheet("color: #9aa0a8;")
        self._charts_layout.addWidget(placeholder)

    def _on_load_muavin(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Muavin Seç", str(Path.home()),
            "Dosyalar (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv)",
        )
        if not paths:
            return
        try:
            frames = [load_muavin(p) for p in paths]
            self._muavin_df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
            self._muavin_paths = paths
            self._lbl_muavin.setText(f"Muavin: {len(paths)} dosya, {len(self._muavin_df)} satır")
            warns = validate_muavin_month_range(self._muavin_df, self._selected_analiz_ayi())
            if warns:
                QMessageBox.warning(self, "Uyarı", "\n".join(warns))
            self._apply_table_filter()
            self._mark_dirty()
        except (MuavinParseError, MizanParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _format_multi_file_label(self, paths: list[str], row_count: int, df: pd.DataFrame | None = None) -> str:
        if not paths:
            return "Yüklenmedi."
        ay_range = ""
        if df is not None and not df.empty and "kaynak_ay" in df.columns:
            aylar = sorted({a for a in df["kaynak_ay"].astype(str) if a and a != "nan"})
            if aylar:
                ay_range = f" ({aylar[0]} – {aylar[-1]})" if len(aylar) > 1 else f" ({aylar[0]})"
        return f"{len(paths)} dosya, {row_count:,} satır{ay_range}".replace(",", ".")

    def _on_load_alis(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Alış Faturaları Seç", str(Path.home()), "Excel (*.xlsx)",
        )
        if not paths:
            return
        try:
            self._alis_fatura_df = load_alis_faturalari_dosyalari(paths)
            self._alis_paths = paths
            self._lbl_alis.setText(
                self._format_multi_file_label(paths, len(self._alis_fatura_df), self._alis_fatura_df)
            )
            self._apply_table_filter()
            self._mark_dirty()
        except (FaturaParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _on_load_satis(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Satış Faturaları Seç", str(Path.home()), "Excel (*.xlsx)",
        )
        if not paths:
            return
        try:
            self._satis_fatura_df = load_satis_faturalari_dosyalari(paths)
            self._satis_paths = paths
            self._lbl_satis.setText(
                self._format_multi_file_label(paths, len(self._satis_fatura_df), self._satis_fatura_df)
            )
            self._apply_table_filter()
            self._mark_dirty()
        except (FaturaParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _on_load_banka(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Banka Hareketleri", str(Path.home()),
            "Dosyalar (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv)",
        )
        if not paths:
            return
        try:
            self._banka_df = load_banka_dosyalari(paths)
            self._banka_paths = paths
            self._lbl_banka.setText(f"Banka: {len(paths)} dosya, {len(self._banka_df):,} satır".replace(",", "."))
            self._apply_table_filter()
            self._mark_dirty()
        except (BankParseError, MizanParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _on_load_tahsilat_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "120 Tahsilat Planı Seç", str(Path.home()), "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            self._tahsilat_plan_df = load_tahsilat_plan(path)
            self._tahsilat_plan_path = path
            self._lbl_tahsilat_plan.setText(
                f"Tahsilat: {Path(path).name} ({len(self._tahsilat_plan_df)} satır)"
            )
            self._preview_combo.setCurrentText("120 Tahsilat")
            self._apply_table_filter()
            self._mark_dirty()
        except (CariPlanParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _on_load_tediye_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "320 Ödeme Planı Seç", str(Path.home()), "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            self._tediye_plan_df = load_tediye_plan(path)
            self._tediye_plan_path = path
            self._lbl_tediye_plan.setText(
                f"Tediye: {Path(path).name} ({len(self._tediye_plan_df)} satır)"
            )
            self._preview_combo.setCurrentText("320 Tediye")
            self._apply_table_filter()
            self._mark_dirty()
        except (CariPlanParseError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Dosya Hatası", str(exc))

    def _maas_rows(self) -> list[PersonelMaas]:
        rows: list[PersonelMaas] = []
        for r in range(self._maas_table.rowCount()):
            ad_item = self._maas_table.item(r, 0)
            if not ad_item or not ad_item.text().strip():
                continue
            def amt(col: int) -> float:
                it = self._maas_table.item(r, col)
                if not it:
                    return 0.0
                try:
                    return float(it.text().replace(".", "").replace(",", "."))
                except ValueError:
                    return 0.0
            rows.append(PersonelMaas(ad=ad_item.text().strip(), resmi_maas=amt(1), harici_maas=amt(2)))
        return rows

    def _on_add_maas_row(self) -> None:
        r = self._maas_table.rowCount()
        self._maas_table.insertRow(r)
        for c, val in enumerate(["", "0", "0", "0"]):
            self._maas_table.setItem(r, c, QTableWidgetItem(val))
        self._mark_dirty()

    def _on_del_maas_row(self) -> None:
        r = self._maas_table.currentRow()
        if r >= 0:
            self._maas_table.removeRow(r)
            self._mark_dirty()

    def _on_maas_cell_changed(self) -> None:
        if self._maas_table_updating:
            return
        self._maas_table_updating = True
        for r in range(self._maas_table.rowCount()):
            try:
                resmi = float((self._maas_table.item(r, 1) or QTableWidgetItem("0")).text().replace(",", "."))
                harici = float((self._maas_table.item(r, 2) or QTableWidgetItem("0")).text().replace(",", "."))
                self._maas_table.setItem(r, 3, QTableWidgetItem(format_tl(resmi + harici).replace(" TL", "")))
            except ValueError:
                pass
        self._maas_table_updating = False
        self._mark_dirty()

    def _on_metrekare_changed(self, value: float) -> None:
        self._dukkan_metrekare = value
        self._mark_dirty()

    def _build_veri_seti(self) -> AnalizVeriSeti:
        ay = self._selected_analiz_ayi()
        return AnalizVeriSeti(
            analiz_ayi=ay,
            muavin_df=self._muavin_df,
            alis_fatura_df=self._alis_fatura_df,
            satis_fatura_df=self._satis_fatura_df,
            banka_df=self._banka_df,
            maas=AylikMaasGirisi(analiz_ayi=ay, personel_maaslari=self._maas_rows()),
            dukkan_metrekare=self._dukkan_metrekare,
            muavin_path=", ".join(Path(p).name for p in self._muavin_paths),
            alis_fatura_path=", ".join(Path(p).name for p in self._alis_paths),
            satis_fatura_path=", ".join(Path(p).name for p in self._satis_paths),
            banka_paths=[Path(p).name for p in self._banka_paths],
            tahsilat_plan_df=self._tahsilat_plan_df,
            tediye_plan_df=self._tediye_plan_df,
            tahsilat_plan_path=Path(self._tahsilat_plan_path).name if self._tahsilat_plan_path else "",
            tediye_plan_path=Path(self._tediye_plan_path).name if self._tediye_plan_path else "",
        )

    def _update_ay_warning(self, analiz_ayi: str) -> None:
        warnings: list[str] = []
        alis_ay = filter_df_by_analiz_ayi(self._alis_fatura_df, "tarih", analiz_ayi)
        satis_ay = filter_df_by_analiz_ayi(self._satis_fatura_df, "tarih", analiz_ayi)
        banka_ay = filter_df_by_analiz_ayi(self._banka_df, "tarih", analiz_ayi)
        if not self._alis_fatura_df.empty and alis_ay.empty:
            warnings.append(f"{analiz_ayi_label(analiz_ayi)} için alış faturası verisi yok.")
        if not self._satis_fatura_df.empty and satis_ay.empty:
            warnings.append(f"{analiz_ayi_label(analiz_ayi)} için satış faturası verisi yok.")
        if not self._banka_df.empty and banka_ay.empty:
            warnings.append(f"{analiz_ayi_label(analiz_ayi)} için banka hareketi yok.")
        if warnings:
            self._ay_warning_label.setText(" ".join(warnings))
            self._ay_warning_label.setVisible(True)
        else:
            self._ay_warning_label.setVisible(False)

    def _run_analysis(self) -> None:
        analiz_ayi = self._selected_analiz_ayi()
        self._update_ay_warning(analiz_ayi)
        veri = self._build_veri_seti()
        if not veri.has_veri:
            QMessageBox.information(self, "Analiz", "Önce en az bir veri dosyası yükleyin.")
            return
        self._btn_analiz.setEnabled(False)
        self._btn_analiz.setText("Hesaplanıyor...")
        QApplication.processEvents()
        try:
            self._report = run_monthly_analysis(veri)
            self._dirty = False
            self._last_analiz_label = analiz_ayi_label(analiz_ayi)
            self._update_analysis_ui()
            self._update_charts_ui()
            self._update_report_preview()
            self._update_status_label()
        except Exception as exc:
            QMessageBox.critical(self, "Analiz Hatası", str(exc))
            self._update_status_label()
        finally:
            self._btn_analiz.setText("Analiz Et")
            if self._has_loaded_data():
                self._btn_analiz.setEnabled(True)

    def _apply_table_filter(self) -> None:
        preview = self._preview_combo.currentText()
        if preview == "Muavin" and not self._muavin_df.empty:
            self._fill_df_table(self._muavin_df, ["tarih", "hesap_kodu", "hesap_adi", "tl_borc", "tl_alacak"])
        elif preview == "Alış Faturaları" and not self._alis_fatura_df.empty:
            self._fill_df_table(self._alis_fatura_df, ["tarih", "cari_adi", "stok_kodu", "net_tutar"])
        elif preview == "Satış Faturaları" and not self._satis_fatura_df.empty:
            self._fill_df_table(self._satis_fatura_df, ["tarih", "cari_adi", "stok_kodu", "net_tutar"])
        elif preview == "Banka" and not self._banka_df.empty:
            self._fill_df_table(
                self._banka_df,
                ["tarih", "banka_adi", "cari_kodu", "evrak_tipi", "giris", "cikis", "bakiye"],
            )
        elif preview == "120 Tahsilat" and not self._tahsilat_plan_df.empty:
            self._fill_df_table(
                self._tahsilat_plan_df,
                ["hesap_kodu", "hesap_adi", "meblag", "satir_bakiye", "vade_kalan_gun"],
            )
        elif preview == "320 Tediye" and not self._tediye_plan_df.empty:
            self._fill_df_table(
                self._tediye_plan_df,
                ["hesap_kodu", "hesap_adi", "meblag", "satir_bakiye", "vade_kalan_gun"],
            )

    def _fill_df_table(self, df: pd.DataFrame, cols: list[str]) -> None:
        display = [c for c in cols if c in df.columns]
        self._table.clear()
        self._table.setColumnCount(len(display))
        self._table.setHorizontalHeaderLabels(display)
        self._table.setRowCount(min(len(df), 500))
        for ri, (_, row) in enumerate(df.head(500).iterrows()):
            for ci, col in enumerate(display):
                val = row[col]
                if col == "tarih" and pd.notna(val):
                    text = val.strftime("%d.%m.%Y")
                elif isinstance(val, (int, float)) and col not in ("hesap_kodu",):
                    text = format_tl(float(val)).replace(" TL", "")
                else:
                    text = str(val)
                self._table.setItem(ri, ci, QTableWidgetItem(text))

    def _clear_layout(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_kpi_card(self, layout: QGridLayout, row: int, col: int, title: str, value: str, color: str = "#4fc3f7") -> None:
        frame = QFrame()
        frame.setStyleSheet(f"background:#252830;border-left:4px solid {color};border-radius:4px;padding:8px;")
        v = QVBoxLayout(frame)
        t = QLabel(title)
        t.setStyleSheet("color:#9aa0a8;font-size:11px;")
        val = QLabel(value)
        val.setStyleSheet("color:#e8eaed;font-size:16px;font-weight:bold;")
        v.addWidget(t)
        v.addWidget(val)
        layout.addWidget(frame, row, col)

    def _fill_simple_table(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for ri, row in enumerate(rows):
            for ci, text in enumerate(row):
                table.setItem(ri, ci, QTableWidgetItem(text))

    def _update_analysis_ui(self) -> None:
        r = self._report
        if not r:
            return

        cfo = r.cfo_uyarilari
        banner = cfo.ozet_metin
        if r.guvenilirlik_aciklama:
            banner = f"{r.guvenilirlik_aciklama}\n{cfo.ozet_metin}"
        self._cfo_banner.setText(banner)
        ctx = r.context
        self._context_label.setText(
            f"Dönem: {ctx.donem_metin} | Muavin: {ctx.muavin_ref} | "
            f"Alış: {ctx.alis_fatura_ref} | Satış: {ctx.satis_fatura_ref} | "
            f"Banka: {ctx.banka_ref} | Tahsilat: {ctx.tahsilat_plan_ref} | "
            f"Tediye: {ctx.tediye_plan_ref}"
        )

        self._clear_layout(self._kpi_grid)
        for i, g in enumerate(cfo.gostergeler):
            color = {"kritik": "#e57373", "uyari": "#ffb74d", "iyi": "#81c784"}.get(g.durum, "#4fc3f7")
            self._add_kpi_card(self._kpi_grid, i // 3, i % 3, g.ad, g.deger, color)

        nakit = r.nakit_akis
        nakit_rows = [
            ["Dönem Başı", format_tl(nakit.donem_basi_mevcut)],
            ["Dönem İçi Girişler", format_tl(nakit.donem_ici_girisler)],
            ["Dönem İçi Çıkışlar", format_tl(nakit.donem_ici_cikislar)],
            ["İç Transfer Giriş (102)", format_tl(nakit.ic_transfer_giris)],
            ["İç Transfer Çıkış (102)", format_tl(nakit.ic_transfer_cikis)],
            ["Operasyonel Giriş (transfer hariç)", format_tl(nakit.giris_transfer_haric)],
            ["Operasyonel Çıkış (transfer hariç)", format_tl(nakit.cikis_transfer_haric)],
            ["Dönem Sonu Net Nakit", format_tl(nakit.donem_sonu_net_nakit)],
        ]
        self._fill_simple_table(self._nakit_table, nakit_rows)

        pl = r.aylik_pl
        self._fill_simple_table(self._pl_table, [
            ["Brüt Kâr (Fatura)", format_tl(pl.brut_kar)],
            ["Operasyonel Gider (Muavin 7xx)", format_tl(pl.toplam_operasyonel_gider)],
            ["Harici Maaş", format_tl(pl.toplam_harici_maas)],
            ["Aylık Net Kâr/Zarar", format_tl(pl.aylik_net_kar)],
        ])

        if r.ay_karsilastirma:
            k = r.ay_karsilastirma
            onceki = analiz_ayi_label(k.onceki_ayi)
            self._karsilastirma_table.parentWidget().setTitle(
                f"Önceki Aya Göre ({onceki} vs {analiz_ayi_label(r.analiz_ayi)})"
            )
            self._fill_simple_table(self._karsilastirma_table, [
                ["Net Kâr/Zarar", format_tl(k.net_kar), format_tl(k.net_kar_onceki), format_tl(k.net_kar_fark)],
                ["Brüt Kâr", format_tl(k.brut_kar), format_tl(k.brut_kar_onceki), format_tl(k.brut_kar_fark)],
                ["Operasyonel Gider", format_tl(k.gider), format_tl(k.gider_onceki), format_tl(k.gider_fark)],
                ["Dönem Sonu Nakit", format_tl(k.nakit_sonu), format_tl(k.nakit_sonu_onceki), format_tl(k.nakit_sonu_fark)],
            ])
        else:
            self._karsilastirma_table.parentWidget().setTitle("Önceki Aya Göre")
            self._karsilastirma_table.setRowCount(0)

        if r.plan_mutabakat:
            pm = r.plan_mutabakat
            mut_rows: list[list[str]] = []
            if pm.tahsilat_plan_acik > 0 or pm.tahsil_edilemeyen > 0:
                mut_rows.append([
                    "Tahsilat (120)",
                    format_tl(pm.tahsilat_plan_acik),
                    format_tl(pm.tahsil_edilemeyen),
                    format_tl(pm.tahsilat_fark),
                ])
            if pm.odeme_plan_acik > 0 or pm.odenmeyen > 0:
                mut_rows.append([
                    "Ödeme (320)",
                    format_tl(pm.odeme_plan_acik),
                    format_tl(pm.odenmeyen),
                    format_tl(pm.odeme_fark),
                ])
            self._fill_simple_table(self._mutabakat_table, mut_rows)
        else:
            self._mutabakat_table.setRowCount(0)

        plan_rows: list[list[str]] = []
        if r.tahsilat_plan and r.tahsilat_plan.hesap_sayisi:
            tp = r.tahsilat_plan
            plan_rows.append([
                "120 Tahsilat",
                format_tl(tp.toplam_acik),
                format_tl(tp.vadesi_gecen),
                format_tl(tp.vadesi_gelmeyen),
                str(tp.hesap_sayisi),
            ])
        if r.tediye_plan and r.tediye_plan.hesap_sayisi:
            op = r.tediye_plan
            plan_rows.append([
                "320 Ödeme",
                format_tl(op.toplam_acik),
                format_tl(op.vadesi_gecen),
                format_tl(op.vadesi_gelmeyen),
                str(op.hesap_sayisi),
            ])
        if r.vade_net is not None:
            plan_rows.append([
                "Vade Neti",
                format_tl(r.vade_net),
                "—", "—", "—",
            ])
        self._fill_simple_table(self._plan_table, plan_rows)

        cari_rows: list[list[str]] = []
        for plan in (r.tahsilat_plan, r.tediye_plan):
            if plan and plan.top_hesaplar:
                for h in plan.top_hesaplar[:5]:
                    cari_rows.append([
                        h.hesap_kodu,
                        h.hesap_adi[:30],
                        format_tl(h.acik_bakiye),
                        format_tl(h.vadesi_gecen),
                        format_tl(h.vadesi_gelmeyen),
                    ])
        self._fill_simple_table(self._plan_cari_table, cari_rows[:10])

        self._fill_simple_table(self._tahsil_table, [
            [s.cari_kodu, format_tl(s.fatura_tutari), format_tl(s.eslesen_banka), format_tl(s.kalan), s.bucket]
            for s in r.yaslandirma.tahsil_edilemeyen[:30]
        ])
        self._fill_simple_table(self._odeme_table, [
            [s.cari_kodu, format_tl(s.fatura_tutari), format_tl(s.eslesen_banka), format_tl(s.kalan), s.bucket]
            for s in r.yaslandirma.odenmeyen[:30]
        ])
        self._fill_simple_table(self._acik_table, [
            [g.tarih, g.banka_adi, g.cari_kodu, g.aciklama[:50], format_tl(g.tutar)]
            for g in r.eslesme.aciklanamayan_giderler[:30]
        ])

        kar_rows: list[list[str]] = []
        if r.fatura_kar and r.fatura_kar.eslesen_kalemler:
            top = sorted(r.fatura_kar.eslesen_kalemler, key=lambda x: x.kar_marji_pct, reverse=True)[:10]
            for k in top:
                kar_rows.append([k.stok_kodu, f"%{k.kar_marji_pct:.1f}", format_tl(k.kar_tutari)])
        self._fill_simple_table(self._kar_table, kar_rows)

        rec_text = "\n\n".join(
            f"[{rec.oncelik.upper()}] {rec.baslik}\n{rec.aciklama}" for rec in r.recommendations[:15]
        )
        self._recommendations_text.setPlainText(rec_text or "Tavsiye yok.")

    def _update_charts_ui(self) -> None:
        while self._charts_layout.count():
            item = self._charts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._report:
            return
        self._charts = build_all_charts(self._report)
        for key, fig in self._charts.items():
            title, subtitle = chart_display_info(key)
            frame = QFrame()
            frame.setStyleSheet("background:#252830;border-radius:6px;padding:8px;")
            vlay = QVBoxLayout(frame)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color:#e8eaed;font-size:13px;font-weight:bold;")
            vlay.addWidget(title_lbl)
            if subtitle:
                sub_lbl = QLabel(subtitle)
                sub_lbl.setWordWrap(True)
                sub_lbl.setStyleSheet("color:#9aa0a8;font-size:10px;")
                vlay.addWidget(sub_lbl)
            canvas = FigureCanvasQTAgg(fig)
            canvas.setMinimumHeight(320)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            vlay.addWidget(canvas)
            self._charts_layout.addWidget(frame)

    def _update_report_preview(self) -> None:
        if not self._report:
            return
        r = self._report
        html = f"<h2>Finansal Analiz — {escape(r.analiz_ayi)}</h2>"
        html += f"<p>{escape(r.summary_text)}</p>"
        for sec in r.summary_sections:
            html += f"<h3>{escape(sec.baslik)}</h3><ul>"
            for line in sec.satirlar:
                html += f"<li>{escape(line)}</li>"
            html += "</ul>"
        self._report_preview.setHtml(html)

    def _ensure_report(self) -> MonthlyAnalysisReport | None:
        if self._report is None:
            QMessageBox.information(
                self,
                "Rapor",
                "Önce «Analiz Et» butonuna basarak analizi çalıştırın.",
            )
            return None
        if self._dirty:
            QMessageBox.information(
                self,
                "Rapor",
                "Veri veya parametreler değişti. Lütfen yeniden «Analiz Et» butonuna basın.",
            )
            return None
        return self._report

    def _export_pdf(self) -> None:
        report = self._ensure_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", f"finans_{report.analiz_ayi}.pdf", "PDF (*.pdf)")
        if path:
            export_pdf(report, Path(path))

    def _export_excel(self) -> None:
        report = self._ensure_report()
        if not report:
            return
        veri = self._build_veri_seti()
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", f"finans_{report.analiz_ayi}.xlsx", "Excel (*.xlsx)")
        if path:
            export_excel(report, veri, Path(path))

    def _export_word(self) -> None:
        report = self._ensure_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Word Kaydet", f"finans_{report.analiz_ayi}.docx", "Word (*.docx)")
        if path:
            export_word(report, Path(path))

    def _export_text(self) -> None:
        report = self._ensure_report()
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Metin Kaydet", f"finans_{report.analiz_ayi}.txt", "Metin (*.txt)")
        if path:
            export_text(report, Path(path))


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    app.setWindowIcon(app_icon())

    if _try_activate_existing_instance():
        return 0

    window = MikRaporWindow()
    server = _start_single_instance_server(window)
    del server
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
