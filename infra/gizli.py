"""
Yerel sır saklama — API anahtarı gibi değerlerin config.json'da şifreli tutulması.

Windows'ta DPAPI (CryptProtectData) kullanılır: şifre yalnızca AYNI Windows kullanıcısı
tarafından çözülebilir; anahtar yönetimi işletim sistemine aittir (ek bağımlılık yok, ctypes).
Diğer platformlarda şifreleme yapılmaz (düz metin) — dosya zaten kullanıcının ev dizinindedir.

Biçim: şifreli değerler "dpapi:<base64>" önekiyle yazılır. Öneksiz değerler düz metin kabul
edilir (geriye dönük uyumluluk: eski config.json'lar okunmaya devam eder ve ilk kayıtta
şifreli biçime geçer).
"""

from __future__ import annotations

import base64
import sys

_PREFIX = "dpapi:"


def _dpapi(func_adi: str, veri: bytes) -> bytes:
    """CryptProtectData / CryptUnprotectData çağrısı (yalnız Windows)."""
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(veri, len(veri))
    girdi = _DataBlob(len(veri), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    cikti = _DataBlob()
    fn = getattr(ctypes.windll.crypt32, func_adi)  # type: ignore[attr-defined]
    if not fn(ctypes.byref(girdi), None, None, None, None, 0, ctypes.byref(cikti)):
        raise OSError(f"{func_adi} başarısız (WinErr {ctypes.GetLastError()})")  # type: ignore[attr-defined]
    try:
        return ctypes.string_at(cikti.pbData, cikti.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(cikti.pbData)  # type: ignore[attr-defined]


def sifrele(deger: str) -> str:
    """Değeri diske yazılacak biçime çevirir (Windows: DPAPI+base64, diğerleri: düz)."""
    if not deger or deger.startswith(_PREFIX):
        return deger
    if not sys.platform.startswith("win"):
        return deger
    try:
        blob = _dpapi("CryptProtectData", deger.encode("utf-8"))
    except Exception:  # noqa: BLE001 — şifreleme başarısızsa düz metne düş (veri kaybı olmasın)
        return deger
    return _PREFIX + base64.b64encode(blob).decode("ascii")


def coz(deger: str) -> str:
    """Diskten okunan değeri çözer. Öneksiz (düz) değer olduğu gibi döner."""
    if not deger or not deger.startswith(_PREFIX):
        return deger
    if not sys.platform.startswith("win"):
        return ""  # başka makinede/platformda çözülemez
    try:
        blob = base64.b64decode(deger[len(_PREFIX):])
        return _dpapi("CryptUnprotectData", blob).decode("utf-8")
    except Exception:  # noqa: BLE001 — bozuk/yabancı kayıt: boş dön (kullanıcı yeniden girer)
        return ""
