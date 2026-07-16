"""
Mikro bağlantı ayarları ekranı (PyQt6).

Kullanıcı kendi Mikro sunucusunun bilgilerini girer; "Bağlantıyı Test Et" ile auth+ağ
doğrulanır, "Kaydet" ile yerel diske yazılır (config.save_config). Bilgiler makineden çıkmaz.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from infra.config import MikroConfig, config_path, load_config, save_config
from infra.mikro_api import MikroClient
from infra.mikro_fetch import fetch_firma_adi


class MikroAyarlarDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mikro Bağlantı Ayarları")
        self.setMinimumWidth(520)
        self._cfg = load_config()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Bu bilgiler yalnızca bu bilgisayarda saklanır ve doğrudan kendi Mikro "
            "sunucunuza bağlanmak için kullanılır. Hiçbir bilgi dışarı gönderilmez. "
            "API anahtarı ve şifre tuzu Windows'ta DPAPI ile şifrelenerek kaydedilir."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #9aa0a8;")
        layout.addWidget(info)

        form = QFormLayout()
        self._base_url = QLineEdit(self._cfg.base_url)
        self._base_url.setPlaceholderText("https://192.168.1.50:443  veya  Tailscale adresi")
        self._api_key = QLineEdit(self._cfg.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._firma_kodu = QLineEdit(self._cfg.firma_kodu)
        self._firma_kodu.setPlaceholderText("örn. 01")
        self._calisma_yili = QSpinBox()
        self._calisma_yili.setRange(2000, 2100)
        self._calisma_yili.setValue(self._cfg.calisma_yili or date.today().year)
        self._kullanici = QLineEdit(self._cfg.kullanici_kodu)
        self._sifre_gun = QLineEdit(self._cfg.sifre_gun)
        self._sifre_gun.setEchoMode(QLineEdit.EchoMode.Password)
        self._sifre_gun.setPlaceholderText("Günlük parola tuzu (boş olabilir)")

        form.addRow("Mikro API adresi:", self._base_url)
        form.addRow("API anahtarı:", self._api_key)
        form.addRow("Firma kodu:", self._firma_kodu)
        form.addRow("Çalışma yılı:", self._calisma_yili)
        form.addRow("Kullanıcı kodu:", self._kullanici)
        form.addRow("Şifre tuzu (SIFRE_GUN):", self._sifre_gun)

        self._firma_adi = QLineEdit(self._cfg.firma_adi)
        self._firma_adi.setPlaceholderText("Boş bırakırsanız Mikro'dan (FIRMALAR.fir_unvan) otomatik çekilir")
        firma_row = QHBoxLayout()
        firma_row.addWidget(self._firma_adi, stretch=1)
        self._btn_firma = QPushButton("Mikro'dan Getir")
        self._btn_firma.clicked.connect(self._on_firma_getir)
        firma_row.addWidget(self._btn_firma)
        form.addRow("Firma adı (raporlarda):", firma_row)

        self._show_secrets = QCheckBox("Anahtar ve şifreyi göster")
        self._show_secrets.toggled.connect(self._on_toggle_secrets)
        form.addRow("", self._show_secrets)

        self._tls_dogrula = QCheckBox("TLS sertifikasını doğrula")
        self._tls_dogrula.setChecked(self._cfg.tls_dogrula)
        self._tls_dogrula.setToolTip(
            "Mikro sunucunuzda geçerli (imzalı) bir sertifika varsa açın.\n"
            "Self-signed sertifika kullanan kurulumlarda (yaygın durum) kapalı bırakın;\n"
            "kapalıyken sertifika doğrulanmaz."
        )
        form.addRow("", self._tls_dogrula)
        layout.addLayout(form)

        path_lbl = QLabel(f"Kayıt yeri: {config_path()}")
        path_lbl.setStyleSheet("color: #9aa0a8; font-size: 10px;")
        path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_lbl)

        test_row = QHBoxLayout()
        self._btn_test = QPushButton("Bağlantıyı Test Et")
        self._btn_test.clicked.connect(self._on_test)
        test_row.addWidget(self._btn_test)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_result, stretch=1)
        layout.addLayout(test_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_firma_getir(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            self._test_result.setText("Önce bağlantı bilgileri gerekli: " + ", ".join(eksik))
            self._test_result.setStyleSheet("color: #ffb74d;")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ad = fetch_firma_adi(MikroClient(cfg))
        except Exception as exc:  # noqa: BLE001 — kullanıcıya hatayı göster
            self._test_result.setText(f"✗ Firma adı alınamadı: {exc}")
            self._test_result.setStyleSheet("color: #e57373;")
            return
        finally:
            QApplication.restoreOverrideCursor()
        if ad:
            self._firma_adi.setText(ad)
            self._test_result.setText(f"✓ Firma adı getirildi: {ad}")
            self._test_result.setStyleSheet("color: #81c784;")
        else:
            self._test_result.setText("Firma ünvanı bulunamadı (FIRMALAR.fir_unvan boş).")
            self._test_result.setStyleSheet("color: #ffb74d;")

    def _on_toggle_secrets(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._api_key.setEchoMode(mode)
        self._sifre_gun.setEchoMode(mode)

    def _current_config(self) -> MikroConfig:
        return MikroConfig(
            base_url=self._base_url.text(),
            api_key=self._api_key.text(),
            firma_kodu=self._firma_kodu.text(),
            calisma_yili=self._calisma_yili.value(),
            kullanici_kodu=self._kullanici.text(),
            sifre_gun=self._sifre_gun.text(),
            firma_adi=self._firma_adi.text(),
            tls_dogrula=self._tls_dogrula.isChecked(),
        ).normalized()

    def _on_test(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            self._test_result.setText("Eksik: " + ", ".join(eksik))
            self._test_result.setStyleSheet("color: #ffb74d;")
            return
        self._test_result.setText("Bağlanılıyor…")
        self._test_result.setStyleSheet("color: #9aa0a8;")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            MikroClient(cfg).ping()
            self._test_result.setText("✓ Bağlantı başarılı.")
            self._test_result.setStyleSheet("color: #81c784;")
        except Exception as exc:  # noqa: BLE001 — kullanıcıya hata mesajını göster
            self._test_result.setText(f"✗ Başarısız: {exc}")
            self._test_result.setStyleSheet("color: #e57373;")
        finally:
            QApplication.restoreOverrideCursor()

    def _on_save(self) -> None:
        cfg = self._current_config()
        eksik = cfg.eksik_alanlar()
        if eksik:
            QMessageBox.warning(self, "Eksik Bilgi", "Şu alanlar zorunlu:\n• " + "\n• ".join(eksik))
            return
        try:
            save_config(cfg)
        except OSError as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))
            return
        self._cfg = cfg
        self.accept()

    def saved_config(self) -> MikroConfig:
        return self._cfg
