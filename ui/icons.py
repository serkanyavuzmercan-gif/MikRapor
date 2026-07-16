"""Kaliteli çizgi ikonlar (QPainter) — emoji yerine mockup A tarzı ince stroke."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ui.styles import MUTED, SUBINK


def _pm(size: int, scale: int = 2) -> tuple[QPixmap, QPainter, float]:
    dpr = float(scale)
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    return pm, p, dpr


def _stroke(color: str, width: float = 1.6) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def icon_gear(size: int = 16, color: str = SUBINK) -> QIcon:
    pm, p, dpr = _pm(size)
    s = size * dpr
    cx, cy = s / 2, s / 2
    r_outer = s * 0.38
    r_inner = s * 0.18
    teeth = 8
    path = QPainterPath()
    for i in range(teeth):
        a0 = (i / teeth) * 360.0
        a1 = ((i + 0.35) / teeth) * 360.0
        a2 = ((i + 0.65) / teeth) * 360.0
        a3 = ((i + 1.0) / teeth) * 360.0
        for ang, rad in ((a0, r_outer * 0.78), (a1, r_outer), (a2, r_outer), (a3, r_outer * 0.78)):
            from math import cos, radians, sin

            x = cx + rad * cos(radians(ang - 90))
            y = cy + rad * sin(radians(ang - 90))
            if path.isEmpty():
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(_stroke(color, 1.5 * dpr))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_pdf(size: int = 16, color: str = SUBINK) -> QIcon:
    pm, p, dpr = _pm(size)
    s = size * dpr
    m = s * 0.18
    # belge
    path = QPainterPath()
    path.moveTo(m + s * 0.08, m)
    path.lineTo(s - m - s * 0.22, m)
    path.lineTo(s - m, m + s * 0.22)
    path.lineTo(s - m, s - m)
    path.lineTo(m + s * 0.08, s - m)
    path.closeSubpath()
    p.setPen(_stroke(color, 1.5 * dpr))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    # köşe katlama
    fold = QPainterPath()
    fold.moveTo(s - m - s * 0.22, m)
    fold.lineTo(s - m - s * 0.22, m + s * 0.22)
    fold.lineTo(s - m, m + s * 0.22)
    p.drawPath(fold)
    # satırlar
    y0 = m + s * 0.38
    for i in range(3):
        y = y0 + i * s * 0.14
        p.drawLine(QPointF(m + s * 0.22, y), QPointF(s - m - s * 0.18, y))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_csv(size: int = 16, color: str = SUBINK) -> QIcon:
    pm, p, dpr = _pm(size)
    s = size * dpr
    m = s * 0.18
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    p.setPen(_stroke(color, 1.5 * dpr))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect, 2 * dpr, 2 * dpr)
    # ızgara
    x1 = m + (s - 2 * m) / 3
    x2 = m + 2 * (s - 2 * m) / 3
    y1 = m + (s - 2 * m) / 3
    y2 = m + 2 * (s - 2 * m) / 3
    p.drawLine(QPointF(x1, m), QPointF(x1, s - m))
    p.drawLine(QPointF(x2, m), QPointF(x2, s - m))
    p.drawLine(QPointF(m, y1), QPointF(s - m, y1))
    p.drawLine(QPointF(m, y2), QPointF(s - m, y2))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_calendar(size: int = 16, color: str = MUTED) -> QIcon:
    pm, p, dpr = _pm(size)
    s = size * dpr
    m = s * 0.16
    p.setPen(_stroke(color, 1.5 * dpr))
    p.setBrush(Qt.BrushStyle.NoBrush)
    body = QRectF(m, m + s * 0.12, s - 2 * m, s - 2 * m - s * 0.08)
    p.drawRoundedRect(body, 2.2 * dpr, 2.2 * dpr)
    p.drawLine(QPointF(m, m + s * 0.32), QPointF(s - m, m + s * 0.32))
    # üst halkalar
    p.drawLine(QPointF(m + s * 0.22, m), QPointF(m + s * 0.22, m + s * 0.22))
    p.drawLine(QPointF(s - m - s * 0.22, m), QPointF(s - m - s * 0.22, m + s * 0.22))
    # gün noktaları
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    for col in range(3):
        for row in range(2):
            x = m + s * 0.28 + col * s * 0.18
            y = m + s * 0.48 + row * s * 0.18
            p.drawEllipse(QPointF(x, y), 1.3 * dpr, 1.3 * dpr)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_chevron_down(size: int = 14, color: str = MUTED) -> QIcon:
    pm, p, dpr = _pm(size)
    s = size * dpr
    p.setPen(_stroke(color, 1.7 * dpr))
    p.setBrush(Qt.BrushStyle.NoBrush)
    mid = s / 2
    p.drawLine(QPointF(s * 0.28, s * 0.38), QPointF(mid, s * 0.62))
    p.drawLine(QPointF(mid, s * 0.62), QPointF(s * 0.72, s * 0.38))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icon_table(size: int = 16, color: str = "#ffffff") -> QIcon:
    """Empty-state CTA için tablo ikonu."""
    return icon_csv(size, color)
