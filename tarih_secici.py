"""
Görünür takvim butonlu tarih alanı — QDateEdit'in gizli okunu telafi eder.
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, pyqtSignal
from PyQt6.QtWidgets import QDateEdit, QHBoxLayout, QPushButton, QWidget


class TarihSecici(QWidget):
    """Tarih metni + sağda 📅 butonu; tıklanınca takvim açılır."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, tarih: QDate, *, genislik: int = 130, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(genislik + 40)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._edit = QDateEdit()
        self._edit.setCalendarPopup(True)
        self._edit.setDisplayFormat("dd.MM.yyyy")
        self._edit.setDate(tarih)
        self._edit.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
        self._edit.setToolTip("Tarihe tıklayın veya sağdaki takvim düğmesine basın")
        self._edit.setObjectName("tarihEdit")
        self._edit.dateChanged.connect(self.dateChanged.emit)

        self._btn = QPushButton("📅")
        self._btn.setObjectName("calBtn")
        self._btn.setFixedWidth(38)
        self._btn.setToolTip("Takvimi aç")
        self._btn.clicked.connect(self._takvim_ac)

        lay.addWidget(self._edit, 1)
        lay.addWidget(self._btn)

    def date(self) -> QDate:
        return self._edit.date()

    def setDate(self, d: QDate) -> None:
        self._edit.blockSignals(True)
        self._edit.setDate(d)
        self._edit.blockSignals(False)

    def blockSignals(self, block: bool) -> bool:  # noqa: A003 — Qt API
        return self._edit.blockSignals(block)

    def _takvim_ac(self) -> None:
        cw = self._edit.calendarWidget()
        if cw is None:
            self._edit.setFocus()
            return
        cw.setSelectedDate(self._edit.date())
        gp = self.mapToGlobal(QPoint(0, self.height() + 2))
        cw.move(gp)
        cw.show()
        cw.raise_()
        cw.setFocus()
