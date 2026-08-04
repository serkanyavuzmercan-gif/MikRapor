"""
Premium sekme kilidi — saf karar mantığı.

MikRapor ücretsiz kurulur; sekmelerin bir kısmı Microsoft Store'dan alınan tek seferlik
bir eklentiyle («add-on») açılır. Bu modülde ağ çağrısı ve Windows API'si YOKTUR:
lisansı okumak `infra/store_lisans.py`nin işi, burası yalnız «ne yapmalı» sorusunu
cevaplar. Böylece kural Windows olmadan da test edilebilir.

BÖLÜNMENİN MANTIĞI — «ne oldu» ücretsiz, «ne yapmalıyım» ücretli:

    ücretsiz : Alacak & Borç · Nakit Akış · Bilanço · Gelir Tablosu
    premium  : Nakit & Kârlılık · Mukayese & Oranlar · Tahmin & Projeksiyon ·
               Reel Değer · Yapay Zekâ Yorumu

Bilanço ve Gelir Tablosu bilerek ÜCRETSİZ: onlar resmî tablolar ve mali müşavir zaten
her ay üretiyor. Komodite olan kısma para istemek ürünü ucuzlatır. Alacak & Borç da
ücretsiz çünkü günlük açılan sekme o — alışkanlık orada kuruluyor.

ŞÜPHEDE KALINCA AÇ. Lisans okunamadığında kilit BASILMAZ; en son bilinen durum
kullanılır. Gerekçe ölçülü: bir hata yüzünden ödemiş müşteriyi kilitlemenin bedeli,
birkaç kişinin fazladan erişmesinden büyüktür — hele yama takvimi yokken.

PREMIUM KENDİLİĞİNDEN GERİ ALINMAZ. `Store hayır dedi` ile `Store cevap veremedi`
pratikte ayrılamıyor: Microsoft hesabına giriş yapmamış ya da lisansı henüz
senkronlanmamış bir kullanıcıda da olumsuz cevap dönüyor. Bu ikisini karıştırıp
otomatik kilitlemek, tam da engellemeye çalıştığımız hatayı üretirdi. Önbellek yalnız
POZİTİF doğrulamayla açılır ve bir daha kendiliğinden kapanmaz.
"""

from __future__ import annotations

from enum import StrEnum

# Sekme kimliği BASLIK'tır — PDF başlığı ve dosya adı da ondan türüyor (kural 5).
UCRETSIZ_SEKMELER = frozenset({
    "Alacak & Borç",
    "Nakit Akış",
    "Bilanço",
    "Gelir Tablosu",
})

PREMIUM_SEKMELER = frozenset({
    "Nakit & Kârlılık",
    "Mukayese & Oranlar",
    "Tahmin & Projeksiyon",
    "Reel Değer",
    "Yapay Zekâ Yorumu",
})

# Premium işareti sekme METNİNE EKLENMEZ, çizilir (ui/app.py: HeaderTabBar).
#
# Metne « ✦» eklemek denendi ve 960px pencerede sekme çubuğunu taşırdı: dokuz sekmenin
# beşi ~19px genişleyince toplam 1033px'e çıkıyor, kullanılabilir alan 935px — son
# sekme görünmez oluyordu (`test_ui_smoke.test_tum_sekmeler_gorunur` yakaladı).
# Çizilen nokta mevcut dolgunun içine düşer, layout'a hiç genişlik eklemez.


class LisansDurumu(StrEnum):
    """Store'dan gelen cevap. `BILINMIYOR` ile `YOK` KARIŞTIRILMAZ."""

    SAHIP = "sahip"          # eklenti bu hesapta kayıtlı
    YOK = "yok"              # Store olumsuz cevap verdi (giriş yapılmamış da olabilir)
    BILINMIYOR = "bilinmiyor"  # okunamadı: Windows değil, paketlenmemiş, ağ yok…


def premium_acik(durum: LisansDurumu, onbellek: bool = False) -> bool:
    """
    Premium sekmeler açık mı?

    `SAHIP` → açık ve bu önbelleğe yazılır (çağıranın işi).
    `YOK` / `BILINMIYOR` → önbellekteki son bilinen değer. `YOK` cevabının kilitleme
    yetkisi YOKTUR; modül docstring'indeki gerekçeye bakınız.
    """
    return True if durum is LisansDurumu.SAHIP else bool(onbellek)


def sekme_kilitli(baslik: str, premium_acik_mi: bool) -> bool:
    """
    Bu sekme kilitli mi?

    Listelenmemiş sekme ÜCRETSİZ sayılır (şüphede kalınca aç). Yeni bir sekme iki
    listeden birine yazılmayı unutursa `test_lisans` kırmızıya döner — varsayılan
    yalnız emniyet supabıdır, kural değil.
    """
    if premium_acik_mi:
        return False
    return baslik in PREMIUM_SEKMELER


def premium_isaretli(baslik: str, premium_acik_mi: bool) -> bool:
    """
    Sekme çubuğunda premium noktası çizilsin mi?

    Kilitli olmakla aynı koşul — ayrı bir kural DEĞİL. Satın alındıktan sonra işaret
    kalkar; ödemiş kullanıcıya hâlâ kilit rozeti göstermek kabul edilemez.
    """
    return sekme_kilitli(baslik, premium_acik_mi)
