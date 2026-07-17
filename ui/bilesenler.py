"""
Ortak küçük UI bileşenleri — durum renkleri, karşılama ekranı, CSV kaydetme, sayı girişleri.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QWidget,
)

from ui.empty_state import build_empty_state
from ui.styles import BAD, MUTED, OK, WARN

DURUM_RENK = {
    "notr": MUTED,
    "iyi": OK,
    "uyari": WARN,
    "hata": BAD,
}


def durum_yaz(label: QLabel, mesaj: str, tur: str = "notr") -> None:
    text = (mesaj or "").strip()
    label.setText(text)
    label.setStyleSheet(f"color: {DURUM_RENK.get(tur, DURUM_RENK['notr'])}; font-weight: 600;")
    label.setVisible(bool(text))


def soru_evet_hayir(
    parent: QWidget | None,
    baslik: str,
    metin: str,
    *,
    varsayilan_evet: bool = True,
) -> bool:
    """Türkçe EVET / HAYIR onay kutusu. True = EVET."""
    kutu = QMessageBox(parent)
    kutu.setIcon(QMessageBox.Icon.Question)
    kutu.setWindowTitle(baslik)
    kutu.setText(metin)
    evet = kutu.addButton("Evet", QMessageBox.ButtonRole.YesRole)
    hayir = kutu.addButton("Hayır", QMessageBox.ButtonRole.NoRole)
    kutu.setDefaultButton(evet if varsayilan_evet else hayir)
    kutu.exec()
    return kutu.clickedButton() is evet


def dialog_kaydet_iptal(buttons: QDialogButtonBox) -> None:
    """QDialogButtonBox Save/Cancel etiketlerini Kaydet / İptal yapar."""
    kaydet = buttons.button(QDialogButtonBox.StandardButton.Save)
    if kaydet is not None:
        kaydet.setText("Kaydet")
    iptal = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    if iptal is not None:
        iptal.setText("İptal")


def hos_geldin(
    emoji: str,
    baslik: str,
    aciklama: str,
    ipucu: str = "",
    *,
    on_cta: Callable[[], None] | None = None,
    cta: str = "",
) -> QWidget:
    """Sekme boşken karşılama — Teal A: illüstrasyon + CTA butonu."""
    del emoji
    cta_text = cta or "Getir"
    if not cta:
        if "Bilanço Getir" in (ipucu or ""):
            cta_text = "Bilanço Getir"
        elif "Gelir Tablosu" in (ipucu or ""):
            cta_text = "Gelir Tablosu Getir"
    aciklama_duz = (aciklama or "").replace("<br>", " ").replace("<br/>", " ")
    # HTML span temizle
    while "<" in aciklama_duz and ">" in aciklama_duz:
        a = aciklama_duz.find("<")
        b = aciklama_duz.find(">", a)
        if b < 0:
            break
        aciklama_duz = aciklama_duz[:a] + aciklama_duz[b + 1 :]
    aciklama_duz = " ".join(aciklama_duz.split())
    return build_empty_state(baslik, aciklama_duz, cta_hint=cta_text, on_cta=on_cta)


def csv_kaydet(parent: QWidget, status: QLabel, varsayilan_ad: str, icerik: str) -> None:
    path, _ = QFileDialog.getSaveFileName(parent, "CSV Kaydet", varsayilan_ad, "CSV (*.csv)")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(icerik)
    except OSError as exc:
        QMessageBox.critical(parent, "CSV Hatası", str(exc))
        return
    durum_yaz(status, f"CSV kaydedildi: {Path(path).name}", "iyi")


def para_spin(maks: float = 1e12) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(-maks, maks)
    sp.setDecimals(0)
    sp.setSingleStep(10000)
    sp.setGroupSeparatorShown(True)
    sp.setSuffix(" TL")
    sp.setMinimumWidth(150)
    return sp


def yuzde_spin(alt: float, ust: float) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(alt, ust)
    sp.setDecimals(1)
    sp.setSingleStep(0.5)
    sp.setSuffix(" %")
    sp.setMinimumWidth(90)
    return sp
