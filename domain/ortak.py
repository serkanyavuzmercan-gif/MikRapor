"""
Ortak yardımcılar — sayı/para biçimlendirme, güvenli dönüştürme ve CSV üretimi.

Bu modül, tüm rapor motorlarında (mizan_bilanco, gelir_tablosu, gercek_durum,
tahsilat_alacak, nakit_akis, tahmin) ve CLI'lerde birebir kopyalanmış olan küçük
yardımcıları tek doğruluk kaynağında toplar. Amaç:

  - DRY: `_f`, `_i`, `tl`, `tl0`, `yuzde` ve CSV sayı/metin biçimlendirmesinin tek yerde olması.
  - Kapsülleme: `tahsilat_alacak`/`nakit_akis`'in `gercek_durum`'un private (`_f`, `_i`,
    `_muh_sinifi`) isimlerine bağımlılığını ortadan kaldırmak.

Saf, bağımlılıksız (yalnız stdlib) — GUI/ağ/DB içermez; kolay test edilir.
"""

from __future__ import annotations

# Kuruş eşiği: bu büyüklüğün altındaki farklar "sıfır" kabul edilir (yuvarlama gürültüsü).
KURUS_ESIK = 0.005


def to_float(v: object) -> float:
    """Değeri güvenle float'a çevirir; çevrilemezse 0.0 döner."""
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def to_int(v: object) -> int:
    """Değeri güvenle int'e çevirir; çevrilemezse -1 (tanımsız) döner."""
    try:
        return int(float(v))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1


def tl(v: float) -> str:
    """1234567.8 -> '1.234.567,80' (işaretli, Türkçe binlik ayracı)."""
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}{s}"


def tl0(v: float) -> str:
    """Yuvarlanmış TL gösterimi (Türkçe binlik) — CLI/test/kompakt gösterim için."""
    return f"{v:,.0f}".replace(",", ".")


def yuzde(v: float) -> str:
    """12.5 -> '%12,5' (Türkçe ondalık)."""
    return ("%" + f"{v:.1f}").replace(".", ",")


def csv_sayi(v: float | None) -> str:
    """CSV için sayı: Türkçe ondalık (virgül); None -> boş hücre. (TR Excel uyumlu)."""
    return "" if v is None else f"{v:.2f}".replace(".", ",")


def csv_metin(x: str) -> str:
    """CSV hücresi için metni temizler: `;` -> `,`, satır sonlarını boşluğa indirger."""
    return str(x).replace(";", ",").replace("\n", " ").strip()


def muh_sinifi(muh_kod: str) -> str:
    """cari_muh_kod / ban_muh_kod ön eki → 'customer' | 'supplier' | ''."""
    ana = str(muh_kod or "").strip().split(".")[0][:3]
    if ana in ("320", "321", "329"):
        return "supplier"
    if ana in ("120", "121"):
        return "customer"
    return ""
