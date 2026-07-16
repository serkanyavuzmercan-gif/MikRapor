"""
Görünür takvim butonlu tarih alanı.

QDateEdit'in dahili drop-down / calendarPopup alanı Windows'ta metin kutusu ile
📅 butonu arasında görünmez tıklama bölgesi bırakır. Bu yüzden:
  - calendarPopup kapalı, NoButtons
  - drop-down QSS ile sıfırlanır
  - takvim yalnızca 📅 butonundan açılır (kendi Popup + QCalendarWidget)
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_ALAN_YUKSEKLIK = 34


class TarihSecici(QWidget):
    """Tarih metni + sağda 📅 butonu; butona basınca takvim açılır."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, tarih: QDate, *, genislik: int = 130, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._cal: QCalendarWidget | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._edit = QDateEdit()
        self._edit.setCalendarPopup(False)
        self._edit.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
        self._edit.setDisplayFormat("dd.MM.yyyy")
        self._edit.setDate(tarih)
        self._edit.setFixedSize(genislik, _ALAN_YUKSEKLIK)
        self._edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._edit.setToolTip("Tarihi yazın veya sağdaki 📅 ile takvimden seçin")
        self._edit.setObjectName("tarihEdit")
        # Global QSS'teki QDateEdit::drop-down { width: 28px } bu alanda boşluk bırakıyor.
        self._edit.setStyleSheet(
            "QDateEdit::drop-down { width: 0px; height: 0px; border: none; image: none; }"
        )
        self._edit.dateChanged.connect(self.dateChanged.emit)

        self._btn = QPushButton("📅")
        self._btn.setObjectName("calBtn")
        self._btn.setFixedSize(38, _ALAN_YUKSEKLIK)
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setToolTip("Takvimi aç")
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.clicked.connect(self._takvim_ac)

        lay.addWidget(self._edit)
        lay.addWidget(self._btn)
        self.setFixedSize(genislik + 38, _ALAN_YUKSEKLIK)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def showEvent(self, event) -> None:  # noqa: ANN001 — Qt override
        super().showEvent(event)
        self._btn.raise_()

    def date(self) -> QDate:
        return self._edit.date()

    def setDate(self, d: QDate) -> None:
        self._edit.blockSignals(True)
        self._edit.setDate(d)
        self._edit.blockSignals(False)

    def blockSignals(self, block: bool) -> bool:  # noqa: A003 — Qt API
        return self._edit.blockSignals(block)

    def _popup_olustur(self) -> None:
        if self._popup is not None:
            return
        self._popup = QWidget(None, Qt.WindowType.Popup)
        self._popup.setObjectName("calPopup")
        pl = QVBoxLayout(self._popup)
        pl.setContentsMargins(6, 6, 6, 6)
        self._cal = QCalendarWidget()
        self._cal.setGridVisible(True)
        self._cal.clicked.connect(self._tarih_secildi)
        self._cal.activated.connect(self._tarih_secildi)
        pl.addWidget(self._cal)

    def _takvim_ac(self) -> None:
        self._popup_olustur()
        assert self._cal is not None and self._popup is not None
        self._cal.setSelectedDate(self._edit.date())
        self._popup.adjustSize()
        anchor = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        pw = self._popup.width()
        self._popup.move(anchor.x() + self._btn.width() - pw, anchor.y())
        self._popup.show()
        self._popup.raise_()
        self._cal.setFocus()

    def _tarih_secildi(self, d: QDate) -> None:
        self._edit.setDate(d)
        if self._popup is not None:
            self._popup.hide()
