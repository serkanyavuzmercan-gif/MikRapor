"""
Sekmeler arası paylaşılan dönem durumu (bas / bit) ve sekme bağlama yardımcıları.

Bir sekmede dönem değişince diğer sekmelerin tarih seçicileri de güncellenir.
Bilanço tek tarihlidir: onun tarihi ortak dönemin bitişine bağlanır.
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

from infra.config import load_config
from ui.tarih_secici import TarihSecici


def _calisma_referans() -> QDate:
    """Kısayol bitiş referansı: çalışma yılı içindeyse bugün, değilse yıl sonu."""
    yil = load_config().calisma_yili or QDate.currentDate().year()
    bugun = QDate.currentDate()
    if bugun.year() == yil:
        return bugun
    if bugun.year() > yil:
        return QDate(yil, 12, 31)
    return QDate(yil, 1, 1)


def kisayol_aralik(kod: str) -> tuple[QDate, QDate]:
    """Bu ay / Bu çeyrek / Bu yıl aralıkları.

    Ay: ay başı → min(ay sonu, bugün).
    Çeyrek: çeyrek başı → çeyrek sonu (ay ile çakışmasın diye tam çeyrek).
    Yıl: 1 Ocak → 31 Aralık.
    """
    ref = _calisma_referans()
    y, m = ref.year(), ref.month()
    if kod == "ay":
        bas = QDate(y, m, 1)
        ay_son = bas.addMonths(1).addDays(-1)
        bit = ref if ay_son > ref else ay_son
        return bas, bit
    if kod == "ceyrek":
        bas_ay = ((m - 1) // 3) * 3 + 1
        bas = QDate(y, bas_ay, 1)
        bit = bas.addMonths(3).addDays(-1)
        return bas, bit
    return QDate(y, 1, 1), QDate(y, 12, 31)


class DonemDurumu(QObject):
    """Tüm rapor sekmelerinde paylaşılan dönem. Bilanço bitiş tarihi = bit."""

    degisti = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        yil = load_config().calisma_yili or QDate.currentDate().year()
        self._bas = QDate(yil, 1, 1)
        bugun = QDate.currentDate()
        self._bit = QDate(yil, 12, 31) if bugun.year() > yil else bugun

    def bas_tarih(self) -> QDate:
        return self._bas

    def bit_tarih(self) -> QDate:
        return self._bit

    def donem_ayarla(
        self,
        *,
        bas: QDate | None = None,
        bit: QDate | None = None,
        bitis_tek: QDate | None = None,
    ) -> None:
        """bitis_tek: bilanço tek tarihi → bit; bas = o yılın 1 Ocak."""
        if bitis_tek is not None:
            yeni_bit = bitis_tek
            yeni_bas = QDate(bitis_tek.year(), 1, 1)
        else:
            yeni_bas = bas if bas is not None else self._bas
            yeni_bit = bit if bit is not None else self._bit
        if yeni_bas == self._bas and yeni_bit == self._bit:
            return
        self._bas, self._bit = yeni_bas, yeni_bit
        self.degisti.emit()


def donem_aralik_bagla(tab: QWidget, donem: DonemDurumu, bas: TarihSecici, bit: TarihSecici) -> None:
    """İki tarihli sekmeyi ortak döneme bağlar (Gelir Tablosu, Nakit & Kârlılık…)."""
    tab._donem_uzaktan = False  # noqa: SLF001

    def uygula() -> None:
        tab._donem_uzaktan = True  # noqa: SLF001
        bas.blockSignals(True)
        bit.blockSignals(True)
        bas.setDate(donem.bas_tarih())
        bit.setDate(donem.bit_tarih())
        bas.blockSignals(False)
        bit.blockSignals(False)
        tab._donem_uzaktan = False  # noqa: SLF001

    def yayinla() -> None:
        if tab._donem_uzaktan:  # noqa: SLF001
            return
        donem.donem_ayarla(bas=bas.date(), bit=bit.date())

    donem.degisti.connect(uygula)
    bas.dateChanged.connect(lambda _d: yayinla())
    bit.dateChanged.connect(lambda _d: yayinla())
    uygula()


def donem_tek_bagla(tab: QWidget, donem: DonemDurumu, tarih: TarihSecici) -> None:
    """Tek tarihli bilanço sekmesini ortak dönemin bitişine bağlar."""
    tab._donem_uzaktan = False  # noqa: SLF001

    def uygula() -> None:
        tab._donem_uzaktan = True  # noqa: SLF001
        tarih.blockSignals(True)
        tarih.setDate(donem.bit_tarih())
        tarih.blockSignals(False)
        tab._donem_uzaktan = False  # noqa: SLF001

    def yayinla() -> None:
        if tab._donem_uzaktan:  # noqa: SLF001
            return
        donem.donem_ayarla(bitis_tek=tarih.date())

    donem.degisti.connect(uygula)
    tarih.dateChanged.connect(lambda _d: yayinla())
    uygula()
