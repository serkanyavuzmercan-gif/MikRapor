"""
Uygulama künyesi — sürüm, telif ve iletişim bilgisi TEK kaynaktan.

PyInstaller paketinde pyproject.toml bulunmaz, o yüzden sürüm burada sabittir.
İkisinin ayrışmaması bir testle güvenceye alınır (bkz. test_surum.py).
"""

from __future__ import annotations

import platform
import sys

SURUM = "1.2.1"
UYGULAMA_ADI = "MikRapor"
ALT_BASLIK = "Finansal Raporlama"
FIRMA = "Hidroteknik Fabr. Malz. San. Tic. A.Ş."
TELIF = "© 2026 Hidroteknik A.Ş. Tüm hakları saklıdır."
ILETISIM = "mikrapor@hidroteknik.com.tr"

PROJE_SORUMLUSU = "Serkan Yavuz Mercan"
GELISTIRICILER = ("Alper Alyaz", "Berra Kaya")

# Microsoft Store — dağıtımın TEK yeri. Premium sekmeler buradan alınan eklentiyle
# açılır; satın alma uygulama içinde değil, bu sayfada tamamlanır (bkz.
# infra/store_lisans.py: neden uygulama içi ödeme penceresi yok).
MAGAZA_STORE_ID = "9NB421K1Z0GB"
MAGAZA_URL = f"ms-windows-store://pdp/?productid={MAGAZA_STORE_ID}"

# Premium eklentisi — İKİ AYRI KİMLİK, KARIŞTIRILMAZ:
#
#   PREMIUM_ADDON_URUN_ID  «mikrapor-premium»  — Partner Center'da BİZİM yazdığımız ad.
#       Lisans okurken `StoreLicense.InAppOfferToken` BUNU döndürür; sahiplik kontrolü
#       bununla yapılır. Oluşturulduktan sonra değiştirilemez.
#
#   PREMIUM_ADDON_STORE_ID «9PF68PSTZNTP»      — Microsoft'un verdiği kimlik.
#       Eklentinin KENDİ ürün sayfasının adresi bundan kurulur; «Satın Al» düğmesi
#       orada. Uygulamanın sayfasına göndermek işe yaramaz: kullanıcı orada
#       «Yüklü / Aç» görür ve premium'u nereden alacağını anlamaz.
#
# İkisini birbirinin yerine kullanmak sessiz arıza üretir: lisans hiç eşleşmez
# (kullanıcı ödediği hâlde kilitli kalır) ya da link boş sayfa açar.
PREMIUM_ADDON_URUN_ID = "mikrapor-premium"
PREMIUM_ADDON_STORE_ID = "9PF68PSTZNTP"


def satin_alma_url() -> str:
    """«Premium'a geç» düğmesinin açacağı sayfa — EKLENTİNİN kendi Store sayfası."""
    if PREMIUM_ADDON_STORE_ID:
        return f"ms-windows-store://pdp/?productid={PREMIUM_ADDON_STORE_ID}"
    return MAGAZA_URL


def eklenti_tanimli() -> bool:
    """Her iki kimlik de yazıldı mı? Biri eksikse satın alma akışı EKSİKTİR."""
    return bool(PREMIUM_ADDON_STORE_ID and PREMIUM_ADDON_URUN_ID)

TANITIM = (
    "MikRapor, Mikro ERP verinizi mali müşavir raporu beklemeden okunur hâle getirir. "
    "Bilanço ve gelir tablosundan nakit akışına, alacak yaşlandırmasından yıllar arası "
    "mukayeseye kadar her rapor doğrudan kendi sunucunuzdaki veriden üretilir."
)

GIZLILIK = (
    "Program kapalı devre çalışır: veriniz yalnız sizin Mikro sunucunuzla bu bilgisayar "
    "arasında kalır. Tek istisna «Yapay Zekâ Yorumu» sekmesidir; orada da veri, ancak "
    "kendi API anahtarınızı girip paylaşım onayını işaretlerseniz dışarı çıkar."
)


def sistem_bilgisi() -> str:
    """Hata bildirimine eklenecek ortam künyesi — sürüm, işletim sistemi, Python."""
    return (f"{UYGULAMA_ADI} {SURUM} · {platform.system()} {platform.release()} · "
            f"Python {sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}")


def hata_bildirim_baglantisi() -> str:
    """
    Konusu ve gövdesi hazır «mailto» adresi.

    Kullanıcıdan sürüm/işletim sistemi istemek yerine baştan ekleriz — hata bildirimi
    böyle eksiksiz gelir.
    """
    from urllib.parse import quote

    konu = quote(f"MikRapor {SURUM} — Hata Bildirimi")
    govde = quote(
        "Sorunu kısaca anlatın:\n\n\n"
        "Hangi adımlardan sonra oldu:\n\n\n"
        f"--- Ortam ---\n{sistem_bilgisi()}\n")
    return f"mailto:{ILETISIM}?subject={konu}&body={govde}"
