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


def _calisma_yili() -> int:
    return load_config().calisma_yili or QDate.currentDate().year()


def _referans_tarih(yil: int) -> QDate:
    """Bir yılın kısayol bitiş referansı: içinde bulunulan yıl ise bugün, değilse yıl sonu."""
    bugun = QDate.currentDate()
    if bugun.year() == yil:
        return bugun
    if bugun.year() > yil:
        return QDate(yil, 12, 31)
    return QDate(yil, 1, 1)


def _calisma_referans() -> QDate:
    """Kısayol bitiş referansı: çalışma yılı içindeyse bugün, değilse yıl sonu."""
    return _referans_tarih(_calisma_yili())


# Toolbar / hızlı dönem grupları — (kod, kısa etiket, isteğe bağlı tooltip)
# Bu ay / Bu yıl: etiket yeterli → tip yok. Çeyrek / yarı: ay aralığı ipucu.
KISAYOL_GRUPLARI: tuple[tuple[tuple[str, str, str], ...], ...] = (
    (
        ("q1", "1. Çeyrek", "Ocak — Mart"),
        ("q2", "2. Çeyrek", "Nisan — Haziran"),
        ("q3", "3. Çeyrek", "Temmuz — Eylül"),
        ("q4", "4. Çeyrek", "Ekim — Aralık"),
    ),
    (
        ("h1", "1. Yarı", "Ocak — Haziran"),
        ("h2", "2. Yarı", "Temmuz — Aralık"),
    ),
    (
        ("ay", "Bu ay", ""),
        ("yil", "Bu yıl", ""),
    ),
)


def kisayol_aralik(kod: str) -> tuple[QDate, QDate]:
    """Dönem kısayolu → (başlangıç, bitiş).

    Çeyrek / yarıyıl / yıl: tam takvim aralığı. Bu ay: ay başı → min(ay sonu, bugün).
    """
    ref = _calisma_referans()
    y, m = ref.year(), ref.month()
    if kod == "ay":
        bas = QDate(y, m, 1)
        ay_son = bas.addMonths(1).addDays(-1)
        bit = ref if ay_son > ref else ay_son
        return bas, bit
    if kod == "yil":
        return QDate(y, 1, 1), QDate(y, 12, 31)
    if kod == "ceyrek":
        bas_ay = ((m - 1) // 3) * 3 + 1
        bas = QDate(y, bas_ay, 1)
        return bas, bas.addMonths(3).addDays(-1)
    if kod in ("q1", "q2", "q3", "q4"):
        i = int(kod[1]) - 1
        bas = QDate(y, i * 3 + 1, 1)
        return bas, bas.addMonths(3).addDays(-1)
    if kod == "h1":
        return QDate(y, 1, 1), QDate(y, 6, 30)
    if kod == "h2":
        return QDate(y, 7, 1), QDate(y, 12, 31)
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
