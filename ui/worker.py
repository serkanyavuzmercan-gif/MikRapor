"""
Arka plan rapor işçisi — ağ çağrıları UI thread'ini kilitlemesin.

RaporWorker, kendisine verilen iş fonksiyonunu ayrı bir QThread'de çalıştırır:
  - is_fn(bildir) çağrılır; `bildir(mesaj)` ile aşama bilgisi UI'ya sinyallenir.
  - Başarıda `bitti(sonuc)`, MikroAPIError'da `hata(mesaj)` yayınlanır.
  - `iptal_et()` işbirlikçi iptaldir: süren HTTP isteği kesilmez (urllib), ama
    sonuç/hata sinyalleri YAYINLANMAZ; istek timeout'una kadar arka planda söner.

İş fonksiyonu WIDGET'A DOKUNMAMALIDIR (Qt nesneleri yalnız ana thread'de) — saf
veri çekme + model kurma yapmalı, sonucu döndürmelidir.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from infra.mikro_api import MikroAPIError

# is_fn(bildir) -> sonuc ; bildir(mesaj) ilerleme geri çağrısı
IsFonksiyonu = Callable[[Callable[[str], None]], Any]


class RaporWorker(QThread):
    """Tek seferlik rapor işi: başlat → ilerleme → bitti | hata."""

    ilerleme = pyqtSignal(str)
    bitti = pyqtSignal(object)
    hata = pyqtSignal(str)

    def __init__(self, is_fn: IsFonksiyonu, parent=None) -> None:
        super().__init__(parent)
        self._is_fn = is_fn
        self._iptal = False

    def iptal_et(self) -> None:
        """İşbirlikçi iptal: bundan sonra hiçbir sinyal yayınlanmaz."""
        self._iptal = True

    def run(self) -> None:  # noqa: D102 — QThread API
        try:
            sonuc = self._is_fn(self._bildir)
        except MikroAPIError as exc:
            if not self._iptal:
                self.hata.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — worker'da yutulmasın, kullanıcıya gösterilsin
            if not self._iptal:
                self.hata.emit(f"Beklenmeyen hata: {exc}")
            return
        if not self._iptal:
            self.bitti.emit(sonuc)

    def _bildir(self, mesaj: str) -> None:
        if not self._iptal:
            self.ilerleme.emit(mesaj)
