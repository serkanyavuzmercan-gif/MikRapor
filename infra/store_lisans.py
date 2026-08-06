"""
Microsoft Store lisans okuyucu — premium eklentisi bu hesapta var mı?

SATIN ALMA BURADA — ölçümle mecbur kalındı. Eklentinin Store sayfası YOKTUR:
`apps.microsoft.com/detail/<eklenti store id>` yayındaki, eksiksiz yapılandırılmış
bir add-on için bile 404/ProductNotFound döner. Kullanıcıyı oraya göndermek onu
kırık bir sayfaya göndermekti. Tek yol `RequestPurchaseAsync`.

UI THREAD'İ BLOKLANMAZ. Satın alma bir zamanlar burada beklenirken canlıda ödeme
penceresi MikRapor'un üstünde değil MASAÜSTÜNDE açıldı ve uygulama «(Yanıt
Vermiyor)» oldu: modal pencerenin sahibi bizim pencereydi, sahibi mesaj
işlemeyince pencere ne öne gelebildi ne odaklanabildi. `satin_al_baslat` işlemi
başlatıp hemen döner, sonucu `completed` geri çağrısıyla verir.

Lisans OKUMASI hâlâ zaman aşımlı bekleniyor: etkileşimsiz, kısa ve arka plan
thread'inden çağrılıyor (`ui/app.py: _lisansi_arkaplanda_oku`).

Hiçbir fonksiyon istisna ATMAZ: okunamazsa `BILINMIYOR`, satın alınamazsa
`BASLATILAMADI`/`YANIT_YOK` döner ve kararı `domain/lisans.py` verir.

VERİ DIŞARI ÇIKMAZ (kural 7). Buradaki çağrılar Windows'un kendi Store servisiyle
konuşur; MikRapor'un okuduğu hiçbir mali veri bu yoldan geçmez. Dışarıya veri gönderen
tek yer Yapay Zekâ Yorumu sekmesi olmaya devam ediyor.
"""

from __future__ import annotations

import logging
import sys

from domain.lisans import LisansDurumu, SatinAlmaSonucu
from infra.surum import (
    MAGAZA_URL,
    PREMIUM_ADDON_STORE_ID,
    PREMIUM_ADDON_URUN_ID,
)

# SINIR YALNIZ LİSANS OKUMASINDA. Satın almaya zaman aşımı KOYULMAZ, çünkü artık
# beklenmiyor: `satin_al_baslat` işlemi başlatıp hemen dönüyor, sonuç geri çağrıyla
# geliyor. Bir zamanlar buraya 900 sn'lik ikinci bir sınır konmuştu; o da UI'yi
# bloklayan tasarımın yamasıydı ve asıl arızayı gizliyordu.
_ZAMAN_ASIMI = 20.0          # lisans okuma — etkileşim yok, hızlı olmalı

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
        lisans = _bekle(_lisans_getir(magaza))
    except Exception as exc:  # noqa: BLE001
        _log.debug("Lisans okunamadı: %s", exc)
        return LisansDurumu.BILINMIYOR
    if lisans is None:
        return LisansDurumu.BILINMIYOR
    try:
        etkin = [ek for ek in lisans.add_on_licenses.values() if ek.is_active]
        # `InAppOfferToken` Partner Center'daki ÜRÜN KİMLİĞİNİ döndürür («mikrapor-premium»),
        # Store ID'yi değil. İkisini karıştırmak hiçbir zaman eşleşmemek demekti:
        # kullanıcı ödediği hâlde kilitli kalırdı.
        if any(ek.in_app_offer_token == PREMIUM_ADDON_URUN_ID for ek in etkin):
            return LisansDurumu.SAHIP
        # Tek eklentisi olan bir üründe token okunamasa bile etkin lisans premium'dur.
        # Şüphede kalınca AÇ (domain/lisans.py): kilitlemenin bedeli daha büyük.
        if etkin:
            _log.debug("Etkin eklenti var ama token eşleşmedi — premium sayıldı")
            return LisansDurumu.SAHIP
    except Exception as exc:  # noqa: BLE001
        _log.debug("Eklenti lisansı ayrıştırılamadı: %s", exc)
        return LisansDurumu.BILINMIYOR
    return LisansDurumu.YOK


def _bekle(coro, sinir: float = _ZAMAN_ASIMI):
    """Coroutine'i zaman aşımıyla koştur — takılan Store UI'yı kilitlemesin."""
    import asyncio

    async def _sinirli():
        return await asyncio.wait_for(coro, timeout=sinir)

    return asyncio.run(_sinirli())


async def _lisans_getir(magaza):
    return await magaza.get_app_license_async()


def magaza_sayfasi_ac() -> bool:
    """
    UYGULAMANIN Store sayfasını açar — «Store sürümünü kur» için, satın alma için DEĞİL.

    Store'dan kurulmamış bir MikRapor'da (GitHub'daki tek dosya .exe, yan yükleme
    MSIX) `StoreContext` hiçbir şey döndürmez ve satın alma yapılamaz. O kullanıcı
    bu sayfada «Al/Yükle» görür; gitmesi gereken yer tam orası.

    Eklentinin kendi sayfasına GÖNDERİLMEZ — öyle bir sayfa yok (modül docstring'i).
    """
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QDesktopServices

    return bool(QDesktopServices.openUrl(QUrl(MAGAZA_URL)))


def _pencereye_bagla(magaza, hwnd: int) -> bool:
    """
    Store nesnesini ana pencereye bağlar (IInitializeWithWindow).

    Sembol ÖLÇÜLDÜ, tahmin edilmedi (Windows runner, store_tani.py):
      winsdk._winrt.initialize_with_window          VAR
      COM apartmanı QApplication sonrası            MAINSTA  ← bu çağrının istediği

    Bağlanamazsa False döner ve satın alma HİÇ DENENMEZ: bağlanmamış çağrı
    sessizce başarısız olur ya da asılır — ikisi de kullanıcıya yalan söyler.
    """
    if not hwnd:
        _log.debug("HWND yok — satın alma penceresi bağlanamaz")
        return False
    try:
        from winsdk._winrt import initialize_with_window
    except ImportError:
        _log.debug("initialize_with_window yok — satın alma yapılamaz")
        return False
    try:
        initialize_with_window(magaza, hwnd)
    except Exception as exc:  # noqa: BLE001
        _log.debug("Pencere bağlanamadı: %s", exc)
        return False
    return True


# Tamamlanana kadar CANLI TUTULUR. WinRT işlemi ve geri çağrısı yalnız yerel
# değişkende tutulsaydı çöp toplayıcı ikisini de silebilir, sonuç hiç gelmezdi.
_bekleyen_satin_alma: list = []


def satin_al_baslat(hwnd: int, geri_cagir) -> SatinAlmaSonucu | None:
    """
    Satın almayı BAŞLATIR ve HEMEN döner; sonuç `geri_cagir(SatinAlmaSonucu)` ile gelir.

    UI THREAD'İ BLOKLANMAZ — bu bir konfor tercihi değil, zorunluluk. Eskiden çağrı
    `asyncio.run` ile burada beklenirken canlıda şu yaşandı: Store'un ödeme penceresi
    HİÇ AÇILMADI, pencere başlığı «(Yanıt Vermiyor)» oldu, uygulama gri kaldı.

    Sebep: `RequestPurchaseAsync` bizim HWND'ye bağlı MODAL bir pencere açıyor ve o
    pencerenin çizilebilmesi için SAHİP THREAD'İN Windows mesajlarını işlemesi
    gerekiyor. Beklerken o thread'i kilitlediğimiz için pencere doğamıyordu bile.
    Zaman aşımını uzatmak çare değildi: sorun beklemenin SÜRESİ değil, kendisiydi.

    Çağrı yine UI thread'inden yapılır (bağlama STA sahip pencere ister), ama
    sonuç `completed` geri çağrısıyla alınır ve kontrol Qt'ye anında geri döner.

    DÖNÜŞ: başlatılamadıysa hatanın kendisi; başladıysa `None` — sonucu bekleyin.
    `geri_cagir` WinRT'nin havuz THREAD'İNDEN çağrılır; arayüze dokunan taraf
    sonucu kendi thread'ine taşımak zorundadır (`ui/rapor_tab.py` sinyalle taşıyor).
    """
    magaza = _winrt_magaza()
    if magaza is None:
        return SatinAlmaSonucu.BASLATILAMADI
    if not _pencereye_bagla(magaza, hwnd):
        return SatinAlmaSonucu.PENCERE_ACILMADI
    try:
        islem = magaza.request_purchase_async(PREMIUM_ADDON_STORE_ID)
    except Exception as exc:  # noqa: BLE001 — WinRT her türlü hatayı atabilir
        _log.debug("Satın alma başlatılamadı: %s", exc)
        return SatinAlmaSonucu.YANIT_YOK

    def _bitti(op, durum) -> None:
        try:
            # AsyncStatus: 0 Started, 1 Completed, 2 Canceled, 3 Error
            sonuc = op.get_results() if int(durum) == 1 else None
        except Exception as exc:  # noqa: BLE001
            _log.debug("Satın alma sonucu okunamadı: %s", exc)
            sonuc = None
        finally:
            _bekleyen_satin_alma.clear()
        # BAŞLADI ama cevap gelmedi. «Başlatılamadı» DEMEYİZ: pencere açılmış,
        # kullanıcı ödemiş bile olabilir.
        geri_cagir(_durum_esle(sonuc))

    _bekleyen_satin_alma.append((islem, _bitti))
    try:
        islem.completed = _bitti
    except Exception as exc:  # noqa: BLE001
        _bekleyen_satin_alma.clear()
        _log.debug("Satın alma geri çağrısı bağlanamadı: %s", exc)
        return SatinAlmaSonucu.YANIT_YOK
    return None


def _durum_esle(sonuc) -> SatinAlmaSonucu:
    """`StorePurchaseStatus` -> `SatinAlmaSonucu`. Sayı değerleri WinRT'de sabittir."""
    if sonuc is None:
        return SatinAlmaSonucu.YANIT_YOK
    try:
        kod = int(getattr(sonuc, "status", sonuc))
    except (TypeError, ValueError):
        return SatinAlmaSonucu.YANIT_YOK
    return {
        0: SatinAlmaSonucu.ALINDI,          # Succeeded
        1: SatinAlmaSonucu.ZATEN_VAR,       # AlreadyPurchased
        2: SatinAlmaSonucu.TAMAMLANMADI,    # NotPurchased
        3: SatinAlmaSonucu.AG_HATASI,       # NetworkError
        4: SatinAlmaSonucu.SUNUCU_HATASI,   # ServerError
    }.get(kod, SatinAlmaSonucu.YANIT_YOK)
