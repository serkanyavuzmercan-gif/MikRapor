"""
MikRapor statik kaynak yolları.
PyInstaller paketinde sys._MEIPASS altından okunur.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap


def project_root() -> Path:
    """Paketlenmiş veya geliştirme ortamı kök dizini (bu dosya ui/ altında — kök bir üst)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    """Yazılabilir veri dizini (exe yanı veya proje kökü)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def asset_path(name: str) -> Path:
    """assets/ altındaki dosyanın tam yolunu döndürür."""
    return project_root() / "assets" / name


def app_icon() -> QIcon:
    """Uygulama pencere ikonu."""
    for name in ("icon.ico", "logo-mark.png", "logo.png"):
        path = asset_path(name)
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


def app_logo_pixmap(size: int = 40) -> QPixmap:
    """Başlık çubuğu için Design A marka görseli (logo-mark → logo fallback)."""
    for name in ("logo-mark.png", "logo.png"):
        png_path = asset_path(name)
        if not png_path.is_file():
            continue
        pm = QPixmap(str(png_path))
        if pm.isNull():
            continue
        return pm.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return QPixmap()
