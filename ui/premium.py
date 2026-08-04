"""
Premium lisans durumu — uygulama ömrü boyunca TEK yerden okunur.

Lisans her sekme için ayrı ayrı sorulmaz: Store çağrısı yavaş olabilir ve dokuz sekme
açılışta dokuz kez sormaz. Bir kez okunur, bellekte tutulur; kullanıcı satın alıp
«Durumu yenile» derse tazelenir.

POZİTİF SONUÇ ÖNBELLEĞE YAZILIR ve bir daha silinmez (`infra/config.py:
premium_onbellek_yaz`). Gerekçesi `domain/lisans.py` docstring'inde: `Store hayır dedi`
ile `Store cevap veremedi` pratikte ayrılamıyor, ikisini karıştırıp otomatik kilitlemek
ödemiş müşteriyi kalıcı olarak dışarıda bırakırdı.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.lisans import LisansDurumu, premium_acik

# Kilitli sekmedeki düğme metni — tek yerde, ekranla PDF'in ayrışması gibi bir risk
# olmasın diye sabit.
PREMIUM_CTA = "Premium'a geç"


@dataclass(frozen=True)
class PremiumDurum:
    acik: bool
    kaynak: LisansDurumu


_durum: PremiumDurum | None = None


def premium_durumu(yenile: bool = False) -> PremiumDurum:
    """Premium açık mı? İlk çağrıda Store'a sorar, sonra bellekten döner."""
    global _durum
    if _durum is not None and not yenile:
        return _durum

    from infra.config import premium_onbellek, premium_onbellek_yaz
    from infra.store_lisans import lisans_durumu

    onbellek = premium_onbellek()
    try:
        kaynak = lisans_durumu()
    except Exception:  # noqa: BLE001 — lisans okuma HİÇBİR koşulda uygulamayı düşürmez
        kaynak = LisansDurumu.BILINMIYOR
    acik = premium_acik(kaynak, onbellek)
    if kaynak is LisansDurumu.SAHIP and not onbellek:
        try:
            premium_onbellek_yaz()
        except OSError:
            pass  # yazılamazsa da bu oturumda açık kalır
    _durum = PremiumDurum(acik=acik, kaynak=kaynak)
    return _durum


def sifirla() -> None:
    """Testler için — bellekteki durumu unutur."""
    global _durum, _satin_alma_bekleniyor
    _durum = None
    _satin_alma_bekleniyor = False


# Kullanıcı Store sayfasına gitti mi? Pencere yeniden odaklanınca lisans YALNIZ bu
# durumda tazelenir — her odak değişiminde Store'a sormak gereksiz yavaşlık olurdu.
_satin_alma_bekleniyor = False


def satin_almaya_gidildi() -> None:
    global _satin_alma_bekleniyor
    _satin_alma_bekleniyor = True


def satin_alma_bekleniyor() -> bool:
    return _satin_alma_bekleniyor
