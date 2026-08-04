"""
Premium sekme kilidi — saf karar mantığı.

MikRapor ücretsiz kurulur; sekmelerin bir kısmı Microsoft Store'dan alınan tek seferlik
bir eklentiyle («add-on») açılır. Bu modülde ağ çağrısı ve Windows API'si YOKTUR:
lisansı okumak `infra/store_lisans.py`nin işi, burası yalnız «ne yapmalı» sorusunu
cevaplar. Böylece kural Windows olmadan da test edilebilir.

PREMIUM OLAN ŞEY «ÜRETİLEN ÇIKTI»DIR, sekmeler değil.

    ücretsiz : dokuz raporun tamamı, ekranda, eksiksiz
    premium  : PDF / CSV dışa aktarma  +  Yapay Zekâ Yorumu

Önce beş sekme kilitleniyordu. Ekranda dokuz sekmenin beşinde amber nokta vardı ve
ürün «yarısı kilitli» görünüyordu — kullanıcının ilk tepkisi de bu oldu. Oysa değer
anı raporu OKUMAK değil, onu müşavire göndermek ya da saklamak: ödeme isteği tam
oraya konunca kimseden bir şey alınmıyor ve kural tek cümleyle anlatılıyor —
«ekranda her şey ücretsiz, dışarı almak premium».

Kilit de tek yere iniyor (dışa aktarma kapısı), dokuz sekmeye dağılmıyor.

VERİLMİŞ SEKME GERİ ALINMAZ. Yeni bir sekmeyi premium doğurtmak sorunsuzdur; bugün
ücretsiz kurup Nakit Akış'ı kullanan müşteriden yarın onu geri almak, hiç vermemekten
kötü karşılanır. Bu yüzden liste dar başlıyor — genişletmek kolay, daraltmak değil.

Yapay Zekâ'nın premium olması ayrıca kendi içinde tutarlı: tek dış çıkış o, tek
değişken maliyet orada.

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
    "Nakit & Kârlılık",
    "Mukayese & Oranlar",
    "Tahmin & Projeksiyon",
    "Reel Değer",
    "Bilanço",
    "Gelir Tablosu",
})

PREMIUM_SEKMELER = frozenset({
    "Yapay Zekâ Yorumu",
})


def disa_aktarim_kilitli(premium_acik_mi: bool) -> bool:
    """
    PDF/CSV dışa aktarma premium mu?

    Veri Sağlığı penceresi BUNA TABİ DEĞİL: o bir rapor değil, kurulumun hâlini
    gösteren bir kontrol. Bozuk kaydı düzeltmeyi sağlayan çıktıyı kilitlemek,
    programın doğru çalışmasını parayla şarta bağlamak olurdu.
    """
    return not premium_acik_mi

# SEKME ÇUBUĞUNDA PREMIUM İŞARETİ YOK.
#
# Önce metne « ✦» eklendi: 960px pencerede çubuğu taşırdı, son sekme görünmez oldu.
# Sonra çizilen nokta denendi — genişlik eklemiyordu ama dokuz sekmenin beşinde amber
# nokta, ekranı «yarısı kilitli» gibi gösteriyordu. Tek premium sekme kalınca işaretin
# kendisi de gereksizleşti: kilit zaten sekmenin İÇİNDE, kendi diliyle anlatılıyor.
# Bir işaret ancak kullanıcının yapabileceği bir şeye işaret ediyorsa değer taşır.


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
