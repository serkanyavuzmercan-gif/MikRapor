"""
Ortak küçük UI bileşenleri — durum renkleri, karşılama ekranı, CSV kaydetme, sayı girişleri.

Sekmelerde kopyalanan yardımcılar tek yerde: renk paleti styles.py Teal A temasıyla uyumludur.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QWidget,
)

from ui.empty_state import build_empty_state
from ui.styles import BAD, MUTED, OK, WARN

# Durum etiketi renkleri (Teal A)
DURUM_RENK = {
    "notr": MUTED,
    "iyi": OK,
    "uyari": WARN,
    "hata": BAD,
}


def durum_yaz(label: QLabel, mesaj: str, tur: str = "notr") -> None:
    """Durum etiketini tek tip renk paletiyle günceller."""
    label.setText(mesaj)
    label.setStyleSheet(f"color: {DURUM_RENK.get(tur, DURUM_RENK['notr'])};")


def hos_geldin(emoji: str, baslik: str, aciklama: str, ipucu: str = "") -> QWidget:
    """Sekme boşken karşılama — Teal A (emoji yok; ipucu CTA metnine çevrilir)."""
    del emoji  # geriye uyumluluk: sekmeler hâlâ EMOJI sabitini geçirir
    cta = "Getir"
    # İpucundan kalın CTA metnini çıkarmaya çalış
    if "Bilanço Getir" in (ipucu or ""):
        cta = "Bilanço Getir"
    elif "Gelir Tablosu" in (ipucu or ""):
        cta = "Gelir Tablosu Getir"
    elif ipucu and "«" in ipucu:
        pass
    # HTML <br> temizle
    aciklama_duz = (aciklama or "").replace("<br>", " ").replace("<br/>", " ")
    return build_empty_state(baslik, aciklama_duz, cta_hint=cta)


def csv_kaydet(parent: QWidget, status: QLabel, varsayilan_ad: str, icerik: str) -> None:
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
    durum_yaz(status, f"CSV kaydedildi: {Path(path).name}", "iyi")


def para_spin(maks: float = 1e12) -> QDoubleSpinBox:
    """TL tutar girişi (binlik ayraçlı, TL sonekli)."""
    sp = QDoubleSpinBox()
    sp.setRange(-maks, maks)
    sp.setDecimals(0)
    sp.setSingleStep(10000)
    sp.setGroupSeparatorShown(True)
    sp.setSuffix(" TL")
    sp.setMinimumWidth(150)
    return sp


def yuzde_spin(alt: float, ust: float) -> QDoubleSpinBox:
    """Yüzde girişi (% sonekli)."""
    sp = QDoubleSpinBox()
    sp.setRange(alt, ust)
    sp.setDecimals(1)
    sp.setSingleStep(0.5)
    sp.setSuffix(" %")
    sp.setMinimumWidth(90)
    return sp
