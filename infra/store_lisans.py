"""
Microsoft Store lisans okuyucu — premium eklentisi bu hesapta var mı?

NE YAPMAZ: satın alma penceresini uygulama içinde AÇMAZ. Store'un `RequestPurchaseAsync`
çağrısı masaüstü uygulamasında pencere tutamacı (HWND) bağlaması ister; bunu Python'dan
COM arayüzü dönüştürerek yapmak gerekiyor ve o yol sürüme bağlı, kırılgan. Bozulursa
sonuç «kimse ödeme yapamıyor» olur. Bunun yerine kullanıcı Store sayfasına gönderilir
(`magaza_sayfasi_ac`) — bir tık uzun, ama asla bozulmaz.

Lisans OKUMAK pencere göstermediği için HWND istemez; riskli kısım yalnız satın alma
penceresiydi ve o hiç yazılmadı.

VERİ DIŞARI ÇIKMAZ (kural 7). Buradaki çağrılar Windows'un kendi Store servisiyle
konuşur; MikRapor'un okuduğu hiçbir mali veri bu yoldan geçmez. Dışarıya veri gönderen
tek yer Yapay Zekâ Yorumu sekmesi olmaya devam ediyor.

Hiçbir fonksiyon istisna ATMAZ: lisans okunamazsa `BILINMIYOR` döner ve kararı
`domain/lisans.py` verir.
"""

from __future__ import annotations

import logging
import sys

from domain.lisans import LisansDurumu
from infra.surum import MAGAZA_URL, PREMIUM_ADDON_STORE_ID

_log = logging.getLogger(__name__)


def _winrt_magaza():
    """StoreContext — yoksa None. Windows dışında ya da winsdk kurulu değilse sessiz."""
    if sys.platform != "win32":
        return None
    try:
        from winsdk.windows.services.store import StoreContext
    except ImportError:
        _log.debug("winsdk yok — lisans okunamıyor, önbellek kullanılacak")
        return None
    try:
        return StoreContext.get_default()
    except Exception as exc:  # noqa: BLE001 — WinRT her türlü hatayı atabilir
        _log.debug("StoreContext kurulamadı: %s", exc)
        return None


def lisans_durumu() -> LisansDurumu:
    """
    Premium eklentisi bu Microsoft hesabında kayıtlı mı?

    `YOK` cevabı KESİN DEĞİLDİR: Store'a giriş yapılmamış ya da lisans henüz
    senkronlanmamış kullanıcıda da döner. Bu yüzden `YOK` tek başına kilit sebebi
    sayılmaz — kararı `domain.lisans.premium_acik` verir.
    """
    magaza = _winrt_magaza()
    if magaza is None:
        return LisansDurumu.BILINMIYOR
    try:
        import asyncio

        lisans = asyncio.run(_lisans_getir(magaza))
    except Exception as exc:  # noqa: BLE001
        _log.debug("Lisans okunamadı: %s", exc)
        return LisansDurumu.BILINMIYOR
    if lisans is None:
        return LisansDurumu.BILINMIYOR
    try:
        for ek in lisans.add_on_licenses.values():
            if ek.is_active and ek.in_app_offer_token == PREMIUM_ADDON_STORE_ID:
                return LisansDurumu.SAHIP
        # Eklenti kimliği henüz tanımlanmadıysa token eşleşmesi yapılamaz; tek bir
        # etkin eklenti varsa onu premium sayarız (Partner Center'da başka eklenti yok).
        if not PREMIUM_ADDON_STORE_ID and any(
                ek.is_active for ek in lisans.add_on_licenses.values()):
            return LisansDurumu.SAHIP
    except Exception as exc:  # noqa: BLE001
        _log.debug("Eklenti lisansı ayrıştırılamadı: %s", exc)
        return LisansDurumu.BILINMIYOR
    return LisansDurumu.YOK


async def _lisans_getir(magaza):
    return await magaza.get_app_license_async()


def magaza_sayfasi_ac() -> bool:
    """
    Store'daki ürün sayfasını açar — satın alma orada tamamlanır.

    Uygulama içi ödeme penceresi bilerek yok (modül docstring'i). Dönüş: açılabildi mi.
    """
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    return bool(QDesktopServices.openUrl(QUrl(MAGAZA_URL)))
