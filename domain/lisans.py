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


class SatinAlmaSonucu(StrEnum):
    """
    Store'un `StorePurchaseStatus` enum'unun karşılığı — WinRT'siz, test edilebilir.

    İSTİSNA DEĞİL ENUM: `RequestPurchaseAsync` başarısızlığı istisna olarak DEĞİL,
    durum koduyla bildirir. Yalnız `try/except` koymak «ağ hatası»nı «başarılı»
    sanmak demekti; her dal ayrı ele alınır.
    """

    ALINDI = "alindi"            # Succeeded
    ZATEN_VAR = "zaten_var"      # AlreadyPurchased
    TAMAMLANMADI = "tamamlanmadi"  # NotPurchased — vazgeçme VE ret aynı kod
    AG_HATASI = "ag_hatasi"      # NetworkError
    SUNUCU_HATASI = "sunucu"     # ServerError
    YAPILAMADI = "yapilamadi"    # Store yok / paket kimliksiz / istisna


def premium_acildi_mi(sonuc: SatinAlmaSonucu) -> bool:
    """
    Premium açılmalı mı?

    `ZATEN_VAR` da açar: kullanıcı daha önce almış ama lisans okuması onu
    görmemiş olabilir — Store'un kendi cevabı, lisans okumasından güçlüdür.

    SATIN ALMA SONUCU POZİTİF DOĞRULAMADIR. Buradan `True` dönünce kilit
    doğrudan açılır; lisansı yeniden okuyup «acaba gerçekten aldı mı» diye
    sormak, kendi kesin bilgini belirsiz bir kaynağa ezdirmektir. Satın almadan
    hemen sonra lisans dağıtımı henüz oturmamış olabilir; o aralıkta kullanıcı
    ödemiş ve ekran kilitli kalmış olurdu.
    """
    return sonuc in (SatinAlmaSonucu.ALINDI, SatinAlmaSonucu.ZATEN_VAR)


def satin_alma_mesaji(sonuc: SatinAlmaSonucu) -> tuple[str, str]:
    """(başlık, gövde) — kullanıcıya gösterilecek metin. SEBEP UYDURULMAZ."""
    if sonuc is SatinAlmaSonucu.ALINDI:
        return ("Premium açıldı",
                "Satın alma tamamlandı. PDF/CSV dışa aktarma ve Yapay Zekâ Yorumu "
                "artık kullanılabilir.")
    if sonuc is SatinAlmaSonucu.ZATEN_VAR:
        return ("Premium zaten sizde",
                "Bu Microsoft hesabında premium eklentisi kayıtlı. Yeniden ücret "
                "alınmadı; premium açıldı.")
    if sonuc is SatinAlmaSonucu.TAMAMLANMADI:
        # «İptal ettiniz» DEMİYORUZ: aynı kod ödemenin reddedilmesinde de dönüyor.
        return ("Satın alma tamamlanmadı",
                "Bir ücret alınmadı. Dilediğiniz zaman tekrar deneyebilirsiniz.")
    if sonuc is SatinAlmaSonucu.AG_HATASI:
        return ("Bağlantı kurulamadı",
                "Microsoft Store'a ulaşılamadı. İnternet bağlantınızı kontrol edip "
                "tekrar deneyin; bir ücret alınmadı.")
    if sonuc is SatinAlmaSonucu.SUNUCU_HATASI:
        return ("Microsoft Store yanıt vermedi",
                "Store tarafında geçici bir sorun var. Biraz sonra tekrar deneyin; "
                "bir ücret alınmadı.")
    return ("Satın alma başlatılamadı",
            "Premium eklentisi yalnız Microsoft Store'dan kurulan MikRapor "
            "sürümünde satın alınabilir. Store sürümünü kurduktan sonra bu "
            "pencereden devam edebilirsiniz.")


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
