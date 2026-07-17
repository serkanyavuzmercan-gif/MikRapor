"""
Dönem tarih seçicileri.

- TarihSecici: tek tarih + takvim popup (popup içinde; klavye ile de yazılır)
- DonemAralikAlani: mockup A tek kutu — «01.01.2026 — 16.07.2026»
  her iki tarih klavyeden düzenlenebilir; takvim ikonu / chevron popup açar
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import icon_calendar, icon_chevron_down
from ui.styles import BORDER_STRONG, INK_SOFT, MUTED, SURFACE

_ALAN_YUKSEKLIK = 36
_INLINE_EDIT_W = 92


def _tarih_edit(tarih: QDate, *, genislik: int, object_name: str = "tarihEdit") -> QDateEdit:
    """Klavyeden yazılabilir, takvim düğmesiz QDateEdit."""
    edit = QDateEdit()
    edit.setCalendarPopup(False)
    edit.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
    edit.setDisplayFormat("dd.MM.yyyy")
    edit.setDate(tarih)
    edit.setFixedHeight(_ALAN_YUKSEKLIK)
    edit.setMinimumWidth(genislik)
    edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    edit.setToolTip("Tarihi klavyeden yazın (gg.aa.yyyy) veya takvimden seçin")
    edit.setObjectName(object_name)
    edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    edit.setStyleSheet(
        "QDateEdit::drop-down { width: 0px; height: 0px; border: none; image: none; }"
    )
    return edit


class TarihSecici(QWidget):
    """Tarih metni + sağda takvim butonu; yazılabilir, butona basınca takvim açılır."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, tarih: QDate, *, genislik: int = 130, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._cal: QCalendarWidget | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._edit = _tarih_edit(tarih, genislik=genislik, object_name="tarihEdit")
        self._edit.setFixedSize(genislik, _ALAN_YUKSEKLIK)
        self._edit.dateChanged.connect(self.dateChanged.emit)

        self._btn = QPushButton()
        self._btn.setObjectName("calBtn")
        self._btn.setIcon(icon_calendar(14))
        self._btn.setIconSize(QSize(14, 14))
        self._btn.setFixedSize(36, _ALAN_YUKSEKLIK)
        self._btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setToolTip("Takvimi aç")
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.clicked.connect(self._takvim_ac)

        lay.addWidget(self._edit)
        lay.addWidget(self._btn)
        self.setFixedSize(genislik + 36, _ALAN_YUKSEKLIK)
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


class DonemAralikAlani(QFrame):
    """
    Mockup A: tek çerçeveli dönem kutusu.

      [📅]  [01.01.2026] — [16.07.2026]  [▾]

    Tarihler klavyeden yazılır; takvim ikonu veya chevron popup açar.
    """

    def __init__(self, donem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from ui.donem import DonemDurumu  # yerel import — döngüyü kır

        assert isinstance(donem, DonemDurumu)
        self._donem = donem
        self._popup: QWidget | None = None
        self._uzaktan = False

        self.setObjectName("donemAralik")
        self.setFixedHeight(_ALAN_YUKSEKLIK)
        self.setMinimumWidth(248)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame#donemAralik {{"
            f"  background: {SURFACE};"
            f"  border: 1px solid {BORDER_STRONG};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame#donemAralik:hover {{ border-color: #9aa6b6; }}"
            f"QDateEdit#donemAralikEdit {{"
            f"  background: transparent; border: none; padding: 0 2px;"
            f"  color: {INK_SOFT}; font-size: 13px; font-weight: 600;"
            f"  min-height: {_ALAN_YUKSEKLIK - 4}px;"
            f"}}"
            f"QDateEdit#donemAralikEdit:focus {{"
            f"  background: #f0fdf9; border-radius: 4px;"
            f"}}"
            f"QDateEdit#donemAralikEdit::drop-down {{"
            f"  width: 0; height: 0; border: none; image: none; background: transparent;"
            f"}}"
            f"QLabel#donemAralikSep {{ color: {MUTED}; font-size: 13px; font-weight: 600;"
            f"  background: transparent; border: none; padding: 0 2px; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 6, 0)
        lay.setSpacing(4)

        self._btn_cal = QPushButton()
        self._btn_cal.setFlat(True)
        self._btn_cal.setIcon(icon_calendar(15))
        self._btn_cal.setIconSize(QSize(15, 15))
        self._btn_cal.setFixedSize(22, 22)
        self._btn_cal.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cal.setToolTip("Takvimle seç")
        self._btn_cal.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_cal.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0; }")
        self._btn_cal.clicked.connect(self._popup_ac)
        lay.addWidget(self._btn_cal, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._bas_edit = _tarih_edit(
            donem.bas_tarih(), genislik=_INLINE_EDIT_W, object_name="donemAralikEdit",
        )
        self._bas_edit.setFixedWidth(_INLINE_EDIT_W)
        lay.addWidget(self._bas_edit, alignment=Qt.AlignmentFlag.AlignVCenter)

        sep = QLabel("—")
        sep.setObjectName("donemAralikSep")
        lay.addWidget(sep, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._bit_edit = _tarih_edit(
            donem.bit_tarih(), genislik=_INLINE_EDIT_W, object_name="donemAralikEdit",
        )
        self._bit_edit.setFixedWidth(_INLINE_EDIT_W)
        lay.addWidget(self._bit_edit, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._btn_chev = QPushButton()
        self._btn_chev.setFlat(True)
        self._btn_chev.setIcon(icon_chevron_down(12))
        self._btn_chev.setIconSize(QSize(12, 12))
        self._btn_chev.setFixedSize(20, 20)
        self._btn_chev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_chev.setToolTip("Takvimle seç")
        self._btn_chev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_chev.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0; }")
        self._btn_chev.clicked.connect(self._popup_ac)
        lay.addWidget(self._btn_chev, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._bas_edit.dateChanged.connect(self._inline_degisti)
        self._bit_edit.dateChanged.connect(self._inline_degisti)
        self._bas_edit.editingFinished.connect(self._inline_bitince)
        self._bit_edit.editingFinished.connect(self._inline_bitince)
        donem.degisti.connect(self._donemden_yukle)
        self._donemden_yukle()

    def _donemden_yukle(self) -> None:
        self._uzaktan = True
        self._bas_edit.blockSignals(True)
        self._bit_edit.blockSignals(True)
        self._bas_edit.setDate(self._donem.bas_tarih())
        self._bit_edit.setDate(self._donem.bit_tarih())
        self._bas_edit.blockSignals(False)
        self._bit_edit.blockSignals(False)
        self._uzaktan = False

    def _inline_degisti(self, _d: QDate) -> None:
        if self._uzaktan:
            return
        self._doneme_yaz()

    def _inline_bitince(self) -> None:
        """Yazım bitince bas ≤ bit garanti et."""
        if self._uzaktan:
            return
        self._doneme_yaz()

    def _doneme_yaz(self) -> None:
        bas = self._bas_edit.date()
        bit = self._bit_edit.date()
        if not bas.isValid() or not bit.isValid():
            return
        if bas > bit:
            bit = bas
            self._uzaktan = True
            self._bit_edit.setDate(bit)
            self._uzaktan = False
        self._donem.donem_ayarla(bas=bas, bit=bit)

    def _popup_ac(self) -> None:
        if self._popup is None:
            self._popup = QWidget(None, Qt.WindowType.Popup)
            self._popup.setObjectName("calPopup")
            pl = QVBoxLayout(self._popup)
            pl.setContentsMargins(12, 12, 12, 12)
            pl.setSpacing(10)

            row1 = QHBoxLayout()
            lbl1 = QLabel("Başlangıç")
            lbl1.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            row1.addWidget(lbl1)
            self._bas = TarihSecici(self._donem.bas_tarih(), genislik=120)
            row1.addWidget(self._bas)
            pl.addLayout(row1)

            row2 = QHBoxLayout()
            lbl2 = QLabel("Bitiş")
            lbl2.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            row2.addWidget(lbl2)
            self._bit = TarihSecici(self._donem.bit_tarih(), genislik=120)
            row2.addWidget(self._bit)
            pl.addLayout(row2)

            self._bas.dateChanged.connect(self._popup_tarih_degisti)
            self._bit.dateChanged.connect(self._popup_tarih_degisti)

        assert self._popup is not None
        self._uzaktan = True
        self._bas.setDate(self._donem.bas_tarih())
        self._bit.setDate(self._donem.bit_tarih())
        self._uzaktan = False
        self._popup.adjustSize()
        pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()
        self._bas._edit.setFocus()  # noqa: SLF001 — popup’ta klavye ile yazılsın
        self._bas._edit.selectAll()  # noqa: SLF001

    def _popup_tarih_degisti(self, _d: QDate) -> None:
        if self._uzaktan:
            return
        bas = self._bas.date()
        bit = self._bit.date()
        if bas > bit:
            bit = bas
            self._uzaktan = True
            self._bit.setDate(bit)
            self._uzaktan = False
        self._donem.donem_ayarla(bas=bas, bit=bit)
