"""Kurumsal NavTip — sekmelerle aynı tooltip kartı (native QToolTip yerine)."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class NavTip(QFrame):
    """Windows’ta kararlı opak kurumsal kart (layered hata yok)."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("navTipCard")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 10, 6)
        root.setSpacing(7)

        accent = QFrame()
        accent.setObjectName("navTipAccent")
        accent.setFixedWidth(2)
        accent.setFixedHeight(20)
        root.addWidget(accent, alignment=Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._eyebrow = QLabel("RAPOR")
        self._eyebrow.setObjectName("navTipEyebrow")
        col.addWidget(self._eyebrow)
        self._title = QLabel()
        self._title.setObjectName("navTipTitle")
        self._title.setWordWrap(False)
        self._title.setMaximumWidth(340)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(title_font)
        col.addWidget(self._title)
        root.addLayout(col)

    def show_text(
        self,
        text: str,
        anchor_global: QPoint,
        *,
        eyebrow: str = "RAPOR",
    ) -> None:
        self._eyebrow.setText(eyebrow)
        # Kısa metinlerde satır kırma (örn. «Temmuz — Aralık»); uzunlarda kaydır
        plain = (text or "").strip()
        wrap = ("\n" in plain) or (len(plain) > 42)
        self._title.setWordWrap(wrap)
        if wrap:
            self._title.setMinimumWidth(0)
            self._title.setMaximumWidth(340)
            self._title.setText(plain)
        else:
            # Kırılmaz tire aralığı — Qt kısa kartta «Temmuz —» / «Aralık» yapmasın
            self._title.setText(plain.replace(" — ", "\u00a0—\u00a0").replace(" - ", "\u00a0—\u00a0"))
            self._title.setMinimumWidth(0)
            self._title.setMaximumWidth(16777215)
            self._title.adjustSize()
            self._title.setMinimumWidth(self._title.sizeHint().width())
        self.adjustSize()
        w, h = self.width(), self.height()
        x = int(anchor_global.x() - w // 2)
        y = int(anchor_global.y() + 6)
        screen = QApplication.screenAt(anchor_global) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.left() + 4, min(x, geo.right() - w - 4))
            y = max(geo.top() + 4, min(y, geo.bottom() - h - 4))
        self.move(x, y)
        self.show()
        self.raise_()

    def hide_tip(self) -> None:
        self.hide()


class NavTipBag(QObject):
    """QWidget hover’da NavTip gösterir; native tooltip’i bastırır."""

    def __init__(
        self,
        widget: QWidget,
        *,
        text: str = "",
        eyebrow: str = "RAPOR",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or widget)
        self._widget = widget
        self._text = (text or "").strip()
        self._eyebrow = eyebrow
        self._tip = NavTip()
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(220)
        self._delay.timeout.connect(self._reveal)
        widget.setToolTip("")
        widget.installEventFilter(self)

    def set_text(self, text: str) -> None:
        self._text = (text or "").strip()
        if not self._text:
            self._cancel()

    def set_eyebrow(self, eyebrow: str) -> None:
        self._eyebrow = eyebrow or "RAPOR"

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._widget:
            et = event.type()
            if et == QEvent.Type.ToolTip:
                return True
            if et == QEvent.Type.Enter:
                if self._text:
                    self._delay.start()
                return False
            if et in (QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.Close):
                self._cancel()
                return False
        return super().eventFilter(obj, event)

    def _reveal(self) -> None:
        if not self._text or not self._widget.isVisible():
            return
        rect = self._widget.rect()
        anchor = self._widget.mapToGlobal(rect.center())
        anchor.setY(self._widget.mapToGlobal(rect.bottomLeft()).y() + 4)
        self._tip.show_text(self._text, anchor, eyebrow=self._eyebrow)

    def _cancel(self) -> None:
        self._delay.stop()
        self._tip.hide_tip()


def bagla_nav_tip(
    widget: QWidget,
    text: str = "",
    *,
    eyebrow: str = "RAPOR",
    parent: QObject | None = None,
) -> NavTipBag:
    """Widget’a kurumsal NavTip bağlar; dönüş değeri set_text için saklanabilir."""
    return NavTipBag(widget, text=text, eyebrow=eyebrow, parent=parent)
