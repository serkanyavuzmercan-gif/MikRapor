"""
Uygulama künyesi — sürüm, telif ve iletişim bilgisi TEK kaynaktan.

PyInstaller paketinde pyproject.toml bulunmaz, o yüzden sürüm burada sabittir.
İkisinin ayrışmaması bir testle güvenceye alınır (bkz. test_surum.py).
"""

from __future__ import annotations

import platform
import sys

SURUM = "1.0.0"
UYGULAMA_ADI = "MikRapor"
ALT_BASLIK = "Finansal Raporlama"
FIRMA = "Hidroteknik Fabr. Malz. San. Tic. A.Ş."
TELIF = "© 2026 Hidroteknik A.Ş. Tüm hakları saklıdır."
ILETISIM = "mikrapor@hidroteknik.com.tr"

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
