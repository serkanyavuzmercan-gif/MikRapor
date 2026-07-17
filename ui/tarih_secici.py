"""
Dönem tarih seçicileri.

- TarihSecici: gg.aa.yyyy satırına klavyeden gün/ay/yıl yazılır + takvim butonu
- DonemAralikAlani: mockup A tek kutu — «01.01.2026 — 16.07.2026» + takvim/chevron
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import icon_calendar, icon_chevron_down
from ui.styles import BORDER_STRONG, INK_SOFT, MUTED, SURFACE

_ALAN_YUKSEKLIK = 36
_FMT = "dd.MM.yyyy"
_MASK = "00.00.0000"


def _metinden_tarih(metin: str) -> QDate | None:
    s = (metin or "").strip()
    if not s or "_" in s:
        return None
    d = QDate.fromString(s, _FMT)
    return d if d.isValid() else None


class _TarihSatiri(QLineEdit):
    """gg.aa.yyyy — gün, ay ve yıl klavyeden serbest yazılır."""

    tarihDegisti = pyqtSignal(QDate)

    def __init__(self, tarih: QDate, *, genislik: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._son_gecerli = tarih if tarih.isValid() else QDate.currentDate()
        self.setObjectName("tarihEdit")
        self.setInputMask(_MASK)
        self.setText(self._son_gecerli.toString(_FMT))
        self.setFixedSize(genislik, _ALAN_YUKSEKLIK)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setToolTip("Tarihi yazın (gg.aa.yyyy) veya sağdaki takvim ile seçin")
        self.setCursorPosition(0)
        self.editingFinished.connect(self._bitince)
        self.textChanged.connect(self._yazildi)

    def date(self) -> QDate:
        return self._son_gecerli

    def setDate(self, d: QDate) -> None:
        if not d.isValid():
            return
        self._son_gecerli = d
        self.blockSignals(True)
        self.setInputMask(_MASK)
        self.setText(d.toString(_FMT))
        self.blockSignals(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # Nokta ile sonraki bölüme (gün → ay → yıl)
        if event.key() in (Qt.Key.Key_Period, Qt.Key.Key_Comma, Qt.Key.Key_Slash):
            pos = self.cursorPosition()
            if pos <= 2:
                self.setCursorPosition(3)
            elif pos <= 5:
                self.setCursorPosition(6)
            event.accept()
            return
        super().keyPressEvent(event)

    def _yazildi(self, _metin: str) -> None:
        """Maske dolunca geçerli tarihi hemen uygula (gün/ay/yıl)."""
        d = _metinden_tarih(self.text())
        if d is None or d == self._son_gecerli:
            return
        self._son_gecerli = d
        self.tarihDegisti.emit(d)

    def _bitince(self) -> None:
        d = _metinden_tarih(self.text())
        if d is None:
            self.setDate(self._son_gecerli)
            return
        if d != self._son_gecerli:
            self._son_gecerli = d
            self.setText(d.toString(_FMT))
            self.tarihDegisti.emit(d)


class TarihSecici(QWidget):
    """Tarih metni + sağda takvim butonu; gün/ay/yıl klavyeden yazılır."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, tarih: QDate, *, genislik: int = 130, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._cal: QCalendarWidget | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._edit = _TarihSatiri(tarih, genislik=genislik)
        self._edit.tarihDegisti.connect(self.dateChanged.emit)

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
        self._edit.setDate(d)

    def blockSignals(self, block: bool) -> bool:  # noqa: A003 — Qt API
        return self._edit.blockSignals(block)

    def odakla(self) -> None:
        """Popup açılınca gün bölümüne odaklan."""
        self._edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self._edit.setCursorPosition(0)

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
        self.dateChanged.emit(d)
        if self._popup is not None:
            self._popup.hide()


class DonemAralikAlani(QFrame):
    """
    Mockup A: tek çerçeveli dönem kutusu.

      [📅]  01.01.2026 — 16.07.2026  [▾]

    Tıklanınca başlangıç/bitiş seçicili popup açılır; DonemDurumu ile senkron kalır.
    """

    def __init__(self, donem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from ui.donem import DonemDurumu  # yerel import — döngüyü kır

        assert isinstance(donem, DonemDurumu)
        self._donem = donem
        self._popup: QWidget | None = None
        self._uzaktan = False

        self.setObjectName("donemAralik")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(_ALAN_YUKSEKLIK)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame#donemAralik {{"
            f"  background: {SURFACE};"
            f"  border: 1px solid {BORDER_STRONG};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame#donemAralik:hover {{ border-color: #9aa6b6; }}"
            f"QLabel#donemAralikText {{ color: {INK_SOFT}; font-size: 13px; font-weight: 600;"
            f"  background: transparent; border: none; }}"
            f"QLabel#donemAralikHint {{ color: {MUTED}; background: transparent; border: none; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 8, 0)
        lay.setSpacing(8)

        cal = QLabel()
        cal.setPixmap(icon_calendar(15).pixmap(15, 15))
        cal.setFixedSize(16, 16)
        lay.addWidget(cal, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._text = QLabel()
        self._text.setObjectName("donemAralikText")
        lay.addWidget(self._text, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        chev = QLabel()
        chev.setPixmap(icon_chevron_down(12).pixmap(12, 12))
        chev.setFixedSize(14, 14)
        lay.addWidget(chev, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._guncelle_metin()
        donem.degisti.connect(self._guncelle_metin)

    def _guncelle_metin(self) -> None:
        bas = self._donem.bas_tarih().toString("dd.MM.yyyy")
        bit = self._donem.bit_tarih().toString("dd.MM.yyyy")
        self._text.setText(f"{bas}  —  {bit}")

    def mousePressEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self._popup_ac()
        super().mousePressEvent(event)

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
        self._bas.odakla()

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
