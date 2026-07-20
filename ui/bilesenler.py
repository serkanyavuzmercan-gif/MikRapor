"""
Ortak küçük UI bileşenleri — durum renkleri, karşılama ekranı, CSV kaydetme, sayı girişleri.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
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


def _bitis_tarihi(bitis: str) -> QDate | None:
    """'yyyy-MM-dd' veya 'yyyy-MM' → QDate (ay için ayın son günü)."""
    s = (bitis or "").strip()
    if len(s) >= 10:
        d = QDate.fromString(s[:10], "yyyy-MM-dd")
        return d if d.isValid() else None
    if len(s) >= 7:
        d = QDate.fromString(s[:7] + "-01", "yyyy-MM-dd")
        if d.isValid():
            return QDate(d.year(), d.month(), d.daysInMonth())
    return None


def donem_gelecek_mi(bitis: str) -> bool:
    d = _bitis_tarihi(bitis)
    return d is not None and d > QDate.currentDate()


def gelecek_donem_uyari_kutusu() -> QFrame:
    """Tek satırlık sarı dikkat kutusu — başlık satırının sağına konur."""
    kutu = QFrame()
    kutu.setObjectName("gelecekDonemUyari")
    kutu.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    lay = QHBoxLayout(kutu)
    lay.setContentsMargins(10, 5, 10, 5)
    lay.setSpacing(0)
    metin = QLabel(
        "Dikkat: Seçtiğiniz dönem verileri daha oluşmadığı için "
        "anlık dönem verileriniz gösteriliyor."
    )
    metin.setObjectName("gelecekDonemUyariMetin")
    metin.setWordWrap(False)
    lay.addWidget(metin)
    return kutu


def baslik_ile_gelecek_uyari(head: QWidget, bitis: str) -> QWidget:
    """Başlık + (gerekirse) sağda tek satır gelecek-dönem uyarısı; ekstra dikey alan yok."""
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(12)
    lay.addWidget(head, 1)
    if donem_gelecek_mi(bitis):
        lay.addWidget(
            gelecek_donem_uyari_kutusu(),
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
    return row


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
    hero_asset: str | None = None,
    hero_fit: str = "cover",
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
    return build_empty_state(
        baslik,
        aciklama_duz,
        cta_hint=cta_text,
        on_cta=on_cta,
        hero_asset=hero_asset,
        hero_fit=hero_fit,
    )


def csv_kaydet(parent: QWidget, status: QLabel | None, varsayilan_ad: str, icerik: str) -> str | None:
    path, _ = QFileDialog.getSaveFileName(parent, "CSV Kaydet", varsayilan_ad, "CSV (*.csv)")
    if not path:
        return None
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(icerik)
    except OSError as exc:
        QMessageBox.critical(parent, "CSV Hatası", str(exc))
        return None
    if status is not None:
        durum_yaz(status, f"CSV kaydedildi: {Path(path).name}", "iyi")
    return path


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
