"""
Ortak küçük UI bileşenleri — durum renkleri, karşılama ekranı, CSV kaydetme, sayı girişleri.

Sekmelerde kopyalanan yardımcılar tek yerde: renk paleti styles.py'deki açık temayla uyumludur.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

# Durum etiketi renkleri (açık tema — styles.py paletiyle uyumlu)
DURUM_RENK = {
    "notr": "#6b7280",
    "iyi": "#15803d",
    "uyari": "#b45309",
    "hata": "#b91c1c",
}

_FONT = "'Segoe UI', system-ui, sans-serif"  # Linux/macOS için fallback zinciri


def durum_yaz(label: QLabel, mesaj: str, tur: str = "notr") -> None:
    """Durum etiketini tek tip renk paletiyle günceller."""
    label.setText(mesaj)
    label.setStyleSheet(f"color: {DURUM_RENK.get(tur, DURUM_RENK['notr'])};")


def hos_geldin(emoji: str, baslik: str, aciklama: str, ipucu: str = "") -> QWidget:
    """Sekme boşken gösterilen ortalanmış karşılama widget'ı."""
    ipucu = ipucu or "Dönemi seçin&nbsp; →&nbsp; <b style='color:#2f6fed;'>Getir</b>'e basın"
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addStretch()
    lbl = QLabel(
        f"<div align='center' style='font-family:{_FONT};'>"
        f"<div style='font-size:46px;'>{emoji}</div>"
        f"<div style='font-size:22px; font-weight:800; color:#374151; margin-top:6px;'>{baslik}</div>"
        f"<div style='color:#6b7280; margin-top:12px; line-height:160%;'>{aciklama}</div>"
        f"<div style='color:#94a3b8; margin-top:16px; font-size:12px;'>{ipucu}</div>"
        f"</div>"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    lay.addStretch()
    return w


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
