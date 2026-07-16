"""
Yerel sır saklama — API anahtarı gibi değerlerin config.json'da şifreli tutulması.

Windows: DPAPI (CryptProtectData) — yalnızca aynı Windows kullanıcısı çözer.
Diğer platformlar: makine+kullanıcı türevli anahtarla yerel şifreleme (`local:` öneki);
dosya zaten 0600, ek olarak diskte düz metin tutulmaz.

Biçimler:
  - `dpapi:<base64>` — Windows DPAPI
  - `local:<base64>` — nonce||hmac||ciphertext (SHA-256 keystream + HMAC)
  - öneksiz — düz metin (eski kayıt; okunur, sonraki kayıtta şifrelenir)
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import os
import sys
from pathlib import Path

_PREFIX_DPAPI = "dpapi:"
_PREFIX_LOCAL = "local:"
_APP_SALT = b"MikRapor.local.v1"


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


def _machine_material() -> bytes:
    """Makine + kullanıcı kimliği (taşınabilir olmayan yerel anahtar malzemesi)."""
    parcalar: list[str] = []
    for yol in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            mid = Path(yol).read_text(encoding="utf-8").strip()
            if mid:
                parcalar.append(mid)
                break
        except OSError:
            continue
    if not parcalar:
        # macOS / fallback: host adı + home yolu
        parcalar.append(os.uname().nodename if hasattr(os, "uname") else "host")
        parcalar.append(str(Path.home()))
    try:
        parcalar.append(getpass.getuser())
    except Exception:  # noqa: BLE001
        parcalar.append("user")
    parcalar.append("MikRapor")
    return "|".join(parcalar).encode("utf-8")


def _local_key() -> bytes:
    return hashlib.pbkdf2_hmac("sha256", _machine_material(), _APP_SALT, 120_000, dklen=32)


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:n])


def _local_sifrele(deger: str) -> str:
    key = _local_key()
    nonce = os.urandom(16)
    plain = deger.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(plain, _keystream(key, nonce, len(plain)), strict=True))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return _PREFIX_LOCAL + base64.b64encode(nonce + mac + ct).decode("ascii")


def _local_coz(deger: str) -> str:
    try:
        raw = base64.b64decode(deger[len(_PREFIX_LOCAL) :])
        if len(raw) < 16 + 32:
            return ""
        nonce, mac, ct = raw[:16], raw[16:48], raw[48:]
        key = _local_key()
        beklenen = hmac.new(key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, beklenen):
            return ""
        plain = bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct)), strict=True))
        return plain.decode("utf-8")
    except Exception:  # noqa: BLE001 — bozuk/yabancı kayıt
        return ""


def sifrele(deger: str) -> str:
    """Değeri diske yazılacak biçime çevirir."""
    if not deger or deger.startswith(_PREFIX_DPAPI) or deger.startswith(_PREFIX_LOCAL):
        return deger
    if sys.platform.startswith("win"):
        try:
            blob = _dpapi("CryptProtectData", deger.encode("utf-8"))
        except Exception:  # noqa: BLE001 — şifreleme başarısızsa yerel forma düş
            return _local_sifrele(deger)
        return _PREFIX_DPAPI + base64.b64encode(blob).decode("ascii")
    return _local_sifrele(deger)


def coz(deger: str) -> str:
    """Diskten okunan değeri çözer. Öneksiz (düz) değer olduğu gibi döner."""
    if not deger:
        return deger
    if deger.startswith(_PREFIX_DPAPI):
        if not sys.platform.startswith("win"):
            return ""  # başka platformda çözülemez
        try:
            blob = base64.b64decode(deger[len(_PREFIX_DPAPI) :])
            return _dpapi("CryptUnprotectData", blob).decode("utf-8")
        except Exception:  # noqa: BLE001
            return ""
    if deger.startswith(_PREFIX_LOCAL):
        return _local_coz(deger)
    return deger
