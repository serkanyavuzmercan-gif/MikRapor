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

from config import MikroConfig, config_path, load_config, save_config
from mikro_api import MikroClient


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
            "sunucunuza bağlanmak için kullanılır. Hiçbir bilgi dışarı gönderilmez."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #9aa0a8;")
        layout.addWidget(info)

        form = QFormLayout()
        self._base_url = QLineEdit(self._cfg.base_url)
        self._base_url.setPlaceholderText("https://192.168.1.50:443  veya  Tailscale adresi")
        self._api_key = QLineEdit(self._cfg.api_key)
        self._firma_kodu = QLineEdit(self._cfg.firma_kodu)
        self._firma_kodu.setPlaceholderText("örn. 26")
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

    def _current_config(self) -> MikroConfig:
        return MikroConfig(
            base_url=self._base_url.text(),
            api_key=self._api_key.text(),
            firma_kodu=self._firma_kodu.text(),
            calisma_yili=self._calisma_yili.value(),
            kullanici_kodu=self._kullanici.text(),
            sifre_gun=self._sifre_gun.text(),
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
