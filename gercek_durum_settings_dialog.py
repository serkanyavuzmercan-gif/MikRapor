"""
Gerçek Durum hesaplama ayarları (PyQt6).

Firma bazlı Mikro kayıt tarzına göre stok sınıflama ve bakiye kaynağı seçilir.
Varsayılan profil MikRapor önerilen ayarlarıdır.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config import config_path
from gercek_durum_ayarlar import (
    ALACAK_BORC_SECENEKLERI,
    ALIS_BAZI_SECENEKLERI,
    GercekDurumAyarlar,
    NAKIT_KAYNAK_SECENEKLERI,
    SATIS_BAZI_SECENEKLERI,
    load_gercek_durum_ayarlar,
    save_gercek_durum_ayarlar,
)


def _combo_secenekler(combo: QComboBox, secenekler: list[tuple[str, str]], secili: str) -> None:
    combo.clear()
    idx = 0
    for i, (kod, etiket) in enumerate(secenekler):
        combo.addItem(etiket, kod)
        if kod == secili:
            idx = i
    combo.setCurrentIndex(idx)


class GercekDurumAyarlarDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gerçek Durum Ayarları")
        self.setMinimumWidth(560)
        self._ayarlar = load_gercek_durum_ayarlar()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Mikro'da kayıt tarzı firmadan firmaya değişir. Bu kurallar yalnızca "
            "«Gerçek Durum» sekmesini etkiler; Bilanço / Gelir Tablosu değişmez. "
            "Şüphede «stok_diag_cli» ve «cari_diag_cli» ile teşhis çalıştırın."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #9aa0a8;")
        layout.addWidget(info)

        form = QFormLayout()
        self._satis = QComboBox()
        _combo_secenekler(self._satis, SATIS_BAZI_SECENEKLERI, self._ayarlar.satis_bazi)
        form.addRow("Satış toplamı:", self._satis)

        self._alis = QComboBox()
        _combo_secenekler(self._alis, ALIS_BAZI_SECENEKLERI, self._ayarlar.alis_bazi)
        form.addRow("Alış toplamı:", self._alis)

        self._nakit = QComboBox()
        _combo_secenekler(self._nakit, NAKIT_KAYNAK_SECENEKLERI, self._ayarlar.nakit_kaynak)
        form.addRow("Nakit bakiyesi:", self._nakit)

        self._alacak_borc = QComboBox()
        _combo_secenekler(self._alacak_borc, ALACAK_BORC_SECENEKLERI, self._ayarlar.alacak_borc_kaynak)
        form.addRow("Alacak / borç:", self._alacak_borc)

        self._kredi_haric = QCheckBox("Kredi bankalarını nakitten hariç tut (300.*, ban_hesap_tip=1)")
        self._kredi_haric.setChecked(self._ayarlar.banka_kredi_haric)
        form.addRow("", self._kredi_haric)

        self._avans_goster = QCheckBox("Müşteri avansı satırını göster")
        self._avans_goster.setChecked(self._ayarlar.musteri_avans_goster)
        form.addRow("", self._avans_goster)

        layout.addLayout(form)

        varsayilan = QPushButton("Varsayılana Dön")
        varsayilan.clicked.connect(self._on_varsayilan)
        layout.addWidget(varsayilan)

        path_lbl = QLabel(f"Kayıt: {config_path()} → «gercek_durum»")
        path_lbl.setStyleSheet("color: #9aa0a8; font-size: 10px;")
        layout.addWidget(path_lbl)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_varsayilan(self) -> None:
        self._ayarlar = GercekDurumAyarlar.varsayilan()
        _combo_secenekler(self._satis, SATIS_BAZI_SECENEKLERI, self._ayarlar.satis_bazi)
        _combo_secenekler(self._alis, ALIS_BAZI_SECENEKLERI, self._ayarlar.alis_bazi)
        _combo_secenekler(self._nakit, NAKIT_KAYNAK_SECENEKLERI, self._ayarlar.nakit_kaynak)
        _combo_secenekler(self._alacak_borc, ALACAK_BORC_SECENEKLERI, self._ayarlar.alacak_borc_kaynak)
        self._kredi_haric.setChecked(self._ayarlar.banka_kredi_haric)
        self._avans_goster.setChecked(self._ayarlar.musteri_avans_goster)

    def _current(self) -> GercekDurumAyarlar:
        return GercekDurumAyarlar(
            satis_bazi=self._satis.currentData() or "sevk",
            alis_bazi=self._alis.currentData() or "fatura",
            nakit_kaynak=self._nakit.currentData() or "gl",
            alacak_borc_kaynak=self._alacak_borc.currentData() or "cari",
            banka_kredi_haric=self._kredi_haric.isChecked(),
            musteri_avans_goster=self._avans_goster.isChecked(),
        )

    def _on_save(self) -> None:
        try:
            self._ayarlar = self._current()
            save_gercek_durum_ayarlar(self._ayarlar)
        except OSError as exc:
            QMessageBox.critical(self, "Kaydedilemedi", str(exc))
            return
        self.accept()

    def ayarlar(self) -> GercekDurumAyarlar:
        return self._ayarlar
