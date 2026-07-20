"""
Nakit & Kârlılık hesaplama ayarları (PyQt6).

Firma bazlı Mikro kayıt tarzına göre stok sınıflama ve bakiye kaynağı seçilir.
Varsayılan profil MikRapor önerilen ayarlarıdır.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from domain.gercek_durum_ayarlar import (
    ALACAK_BORC_SECENEKLERI,
    ALIS_BAZI_SECENEKLERI,
    NAKIT_KAYNAK_SECENEKLERI,
    SATIS_BAZI_SECENEKLERI,
    GercekDurumAyarlar,
)
from infra.config import config_path, load_gercek_durum_ayarlar, save_gercek_durum_ayarlar
from ui.icons import icon_chevron_down
from ui.nav_tip import bagla_nav_tip
from ui.styles import ACCENT, ACCENT_SOFT, BORDER, BORDER_STRONG, MUTED, NAVY, NAVY_SOFT, SURFACE

_CHEVRON_PNG = Path(__file__).resolve().parent.parent / "assets" / "chevron-down-teal.png"


def _chevron_qss_url() -> str:
    """QSS image: yolu oluştur (yoksa çiz)."""
    if not _CHEVRON_PNG.exists():
        _CHEVRON_PNG.parent.mkdir(parents=True, exist_ok=True)
        icon_chevron_down(12, ACCENT).pixmap(12, 12).save(str(_CHEVRON_PNG), "PNG")
    # QSS Windows’ta forward slash ister
    return _CHEVRON_PNG.as_posix()


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
        self.setWindowTitle("Nakit & Kârlılık — Hesaplama")
        self.setObjectName("gdAyarDialog")
        self.setMinimumWidth(440)
        self.setMaximumWidth(480)
        self._ayarlar = load_gercek_durum_ayarlar()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # —— Lacivert başlık ——
        baslik = QFrame()
        baslik.setObjectName("gdAyarBaslik")
        bl = QVBoxLayout(baslik)
        bl.setContentsMargins(18, 16, 18, 14)
        bl.setSpacing(4)
        ey = QLabel("NAKİT & KÂRLILIK")
        ey.setObjectName("gdAyarEyebrow")
        bl.addWidget(ey)
        bas = QLabel("Hesaplama kuralları")
        bas.setObjectName("gdAyarBaslikYazi")
        bl.addWidget(bas)
        acik = QLabel(
            "Yalnızca bu sekmeyi etkiler. Kurallar «Raporu Getir» sırasında uygulanır; "
            "PDF/CSV ekrandaki aynı sonucu dışa aktarır. Bilanço / Gelir değişmez."
        )
        acik.setObjectName("gdAyarAciklama")
        acik.setWordWrap(True)
        bl.addWidget(acik)
        root.addWidget(baslik)

        govde = QWidget()
        gl = QVBoxLayout(govde)
        gl.setContentsMargins(18, 16, 18, 16)
        gl.setSpacing(12)

        kart = QFrame()
        kart.setObjectName("gdAyarKart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(14, 12, 14, 12)
        kl.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._satis = QComboBox()
        self._satis.setObjectName("gdAyarCombo")
        _combo_secenekler(self._satis, SATIS_BAZI_SECENEKLERI, self._ayarlar.satis_bazi)
        form.addRow(self._lbl("Satış toplamı"), self._satis)

        self._alis = QComboBox()
        self._alis.setObjectName("gdAyarCombo")
        _combo_secenekler(self._alis, ALIS_BAZI_SECENEKLERI, self._ayarlar.alis_bazi)
        form.addRow(self._lbl("Alış toplamı"), self._alis)

        self._nakit = QComboBox()
        self._nakit.setObjectName("gdAyarCombo")
        _combo_secenekler(self._nakit, NAKIT_KAYNAK_SECENEKLERI, self._ayarlar.nakit_kaynak)
        form.addRow(self._lbl("Nakit bakiyesi"), self._nakit)

        self._alacak_borc = QComboBox()
        self._alacak_borc.setObjectName("gdAyarCombo")
        _combo_secenekler(self._alacak_borc, ALACAK_BORC_SECENEKLERI, self._ayarlar.alacak_borc_kaynak)
        form.addRow(self._lbl("Alacak / borç"), self._alacak_borc)
        kl.addLayout(form)

        self._kredi_haric = QCheckBox("Kredi bankalarını nakitten hariç tut")
        self._kredi_haric.setObjectName("gdAyarCheck")
        bagla_nav_tip(
            self._kredi_haric, "300.* · ban_hesap_tip=1", eyebrow="HESAPLAMA", parent=self)
        self._kredi_haric.setChecked(self._ayarlar.banka_kredi_haric)
        kl.addWidget(self._kredi_haric)

        self._avans_goster = QCheckBox("Müşteri avansı satırını göster")
        self._avans_goster.setObjectName("gdAyarCheck")
        self._avans_goster.setChecked(self._ayarlar.musteri_avans_goster)
        kl.addWidget(self._avans_goster)

        gl.addWidget(kart)

        alt = QHBoxLayout()
        alt.setSpacing(8)
        varsayilan = QPushButton("Varsayılana dön")
        varsayilan.setObjectName("ghostBtn")
        varsayilan.setCursor(Qt.CursorShape.PointingHandCursor)
        varsayilan.clicked.connect(self._on_varsayilan)
        alt.addWidget(varsayilan)
        alt.addStretch(1)
        gl.addLayout(alt)

        path_lbl = QLabel(f"Kayıt: {config_path().name} → gercek_durum")
        path_lbl.setObjectName("gdAyarPath")
        gl.addWidget(path_lbl)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        from ui.bilesenler import dialog_kaydet_iptal
        dialog_kaydet_iptal(buttons)
        kaydet = buttons.button(QDialogButtonBox.StandardButton.Save)
        if kaydet is not None:
            kaydet.setObjectName("primaryBtn")
            kaydet.setCursor(Qt.CursorShape.PointingHandCursor)
        gl.addWidget(buttons)

        root.addWidget(govde)
        self._uygula_stil()

    @staticmethod
    def _lbl(metin: str) -> QLabel:
        lbl = QLabel(metin)
        lbl.setObjectName("gdAyarEtiket")
        return lbl

    def _uygula_stil(self) -> None:
        ok_url = _chevron_qss_url()
        self.setStyleSheet(
            f"""
            QDialog#gdAyarDialog {{ background: {SURFACE}; }}
            QFrame#gdAyarBaslik {{
                background: {NAVY};
                border: none;
            }}
            QLabel#gdAyarEyebrow {{
                color: #99f6e4;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }}
            QLabel#gdAyarBaslikYazi {{
                color: #f1f5f9;
                font-size: 16px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#gdAyarAciklama {{
                color: #a8bdd4;
                font-size: 12px;
                background: transparent;
            }}
            QFrame#gdAyarKart {{
                background: {NAVY_SOFT};
                border: 1px solid {BORDER};
                border-left: 3px solid {ACCENT};
                border-radius: 10px;
            }}
            QLabel#gdAyarEtiket {{
                color: {NAVY};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QComboBox#gdAyarCombo {{
                background: {SURFACE};
                color: {NAVY};
                border: 1px solid #c5d0de;
                border-radius: 8px;
                padding: 6px 36px 6px 10px;
                min-height: 24px;
            }}
            QComboBox#gdAyarCombo:hover {{ border-color: {ACCENT}; }}
            QComboBox#gdAyarCombo:focus {{ border: 1px solid {ACCENT}; }}
            QComboBox#gdAyarCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border: none;
                border-left: 1px solid {BORDER_STRONG};
                background: {ACCENT_SOFT};
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
            }}
            QComboBox#gdAyarCombo::down-arrow {{
                image: url({ok_url});
                width: 12px;
                height: 12px;
            }}
            QCheckBox#gdAyarCheck {{
                color: {NAVY};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
            QLabel#gdAyarPath {{
                color: {MUTED};
                font-size: 10px;
                background: transparent;
            }}
            """
        )

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
