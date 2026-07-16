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
    ico_path = asset_path("icon.ico")
    if ico_path.is_file():
        return QIcon(str(ico_path))
    png_path = asset_path("logo.png")
    if png_path.is_file():
        return QIcon(str(png_path))
    return QIcon()


def app_logo_pixmap(size: int = 40) -> QPixmap:
    """Başlık çubuğu için logo görseli."""
    png_path = asset_path("logo.png")
    if not png_path.is_file():
        return QPixmap()
    pm = QPixmap(str(png_path))
    if pm.isNull():
        return QPixmap()
    return pm.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
