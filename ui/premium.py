"""
Premium lisans durumu — uygulama ömrü boyunca TEK yerden okunur.

AÇILIŞ YOLUNDA STORE'A SORULMAZ. `premium_durumu()` yalnız yerel önbelleği okur ve
anında döner. Sebep ölçüldü: `kilitli()` → `_bos_ekran()` → `_build()` zinciri dokuz
sekmenin kurulumunda, UI thread'inde koşuyor. Oraya senkron bir WinRT çağrısı koymak,
Store yavaşladığında uygulamayı AÇILIŞTA dondurur. (Bugün fark edilmiyordu çünkü
`winsdk` paketlenmemişti ve import anında hata veriyordu — yani lisans hiç okunmuyordu.)

Store'a iki yerde sorulur, ikisi de açılış yolunun dışında:
  • `premium_durumu(yenile=True)` — arka plan işçisinden, pencere açıldıktan sonra
  • satın alma sonrası — ki orada zaten cevabı biliyoruz

POZİTİF SONUÇ ÖNBELLEĞE YAZILIR ve bir daha silinmez (`infra/config.py:
premium_onbellek_yaz`). Gerekçesi `domain/lisans.py` docstring'inde: `Store hayır dedi`
ile `Store cevap veremedi` pratikte ayrılamıyor, ikisini karıştırıp otomatik kilitlemek
ödemiş müşteriyi kalıcı olarak dışarıda bırakırdı.

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
    """
    Premium açık mı?

    `yenile=False` (varsayılan): AĞA ÇIKMAZ. Yerel önbellekten anında döner —
    açılış yolundan çağrıldığı için burada Store'a sormak yasak.
    `yenile=True`: Store'a sorar. Yalnız arka plan işçisinden çağrılır.
    """
    global _durum
    if _durum is not None and not yenile:
        return _durum

    from infra.config import premium_onbellek, premium_onbellek_yaz

    if not yenile:
        # Ağa çıkmayan hızlı yol: yalnız önbellek.
        _durum = PremiumDurum(acik=bool(premium_onbellek()),
                              kaynak=LisansDurumu.BILINMIYOR)
        return _durum

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


def premium_ac() -> None:
    """
    Satın alma başarılı — premium'u AÇ ve önbelleğe yaz.

    Lisansı yeniden okuyup teyit ETMİYORUZ: satın almadan hemen sonra lisans
    dağıtımı henüz oturmamış olabilir ve o aralıkta «yok» cevabı gelirse kullanıcı
    ödediği hâlde kilitli kalırdı. Store'un satın alma cevabı, lisans okumasından
    daha güçlü bir pozitif doğrulamadır (`domain/lisans.py: premium_acildi_mi`).
    """
    global _durum
    _durum = PremiumDurum(acik=True, kaynak=LisansDurumu.SAHIP)
    try:
        from infra.config import premium_onbellek_yaz

        premium_onbellek_yaz()
    except OSError:
        pass  # yazılamazsa da bu oturumda açık kalır


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
