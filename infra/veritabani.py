"""
Veritabanı kataloğu — hangi yıl hangi Mikro veritabanında?

Mikro'da veritabanını **firma kodu** seçer; `calisma_yili` yalnızca auth gövdesinde
gider ve tek veritabanlı kurulumlarda hiçbir şeyi değiştirmez. Bir veritabanı birden
çok yıl taşıyabilir — canlı kurulumda:

    firma 20 → 2020…2025        firma 26 → 2026 (ileride 2027-2030)

Kullanıcı bunu bilmek zorunda kalmamalı: tarih aralığını seçer, program veriyi
nerede duruyorsa oradan okur. Bu modül o eşlemeyi kurar.

Kapsam her firma için TEK ucuz sorguyla (MIN/MAX fis_tarih, indeks araması) bulunur
ve süreç boyunca önbellekte tutulur — her rapor için yeniden yoklamak israf olur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from infra.config import MikroConfig
from infra.mikro_api import MikroAPIError, MikroClient
from infra.mikro_fetch import fetch_yil_araligi

_AYIRAC = re.compile(r"[,;\s]+")
_SAYISAL_ARALIK = re.compile(r"^(\d+)-(\d+)$")
_AZAMI_TARANACAK_FIRMA = 500


@dataclass(frozen=True)
class FirmaKapsami:
    """Bir Mikro veritabanının (firma kodunun) taşıdığı yıl aralığı."""
    firma_kodu: str
    ilk_yil: int
    son_yil: int

    def icerir(self, yil: int) -> bool:
        return self.ilk_yil <= yil <= self.son_yil

    @property
    def gecerli(self) -> bool:
        return bool(self.firma_kodu) and self.ilk_yil > 0 and self.son_yil >= self.ilk_yil


def firma_kodlari(cfg: MikroConfig) -> list[str]:
    """
    Ayarlardaki firma kodu listesi — «20, 26» veya «001-100» gibi.

    Sayısal aralık, yüzlerce yıl veritabanı olan kurulumda kodları tek tek yazma
    gereğini kaldırır. Başındaki sıfırlar korunur (``001-003`` → ``001, 002, 003``).
    Yanlışlıkla aşırı büyük tarama başlatmamak için en çok 500 kod genişletilir.

    Sıra korunur, tekrarlar elenir: kullanıcının yazdığı sıra kapsam çakışmasında
    öncelik anlamına gelir.
    """
    ham = (getattr(cfg, "firma_kodlari", "") or "").strip()
    parcalar: list[str] = []
    for parca in ([p for p in _AYIRAC.split(ham) if p] if ham else []):
        aralik = _SAYISAL_ARALIK.fullmatch(parca)
        if aralik:
            ilk, son = int(aralik.group(1)), int(aralik.group(2))
            adet = son - ilk + 1
            if 0 < adet <= _AZAMI_TARANACAK_FIRMA:
                hane = max(len(aralik.group(1)), len(aralik.group(2)))
                parcalar.extend(f"{kod:0{hane}d}" for kod in range(ilk, son + 1))
                continue
        parcalar.append(parca)
    if not parcalar and cfg.firma_kodu:
        parcalar = [cfg.firma_kodu.strip()]
    gorulen: set[str] = set()
    return [p for p in parcalar if not (p in gorulen or gorulen.add(p))]


def firma_client(cfg: MikroConfig, firma_kodu: str) -> MikroClient:
    """Aynı bağlantı, farklı veritabanı — yalnız firma kodu değişir."""
    return MikroClient(replace(cfg.normalized(), firma_kodu=firma_kodu))


# (base_url, kullanıcı, firma listesi) → kapsamlar. Süreç ömrü boyunca geçerli.
_ONBELLEK: dict[tuple[str, str, tuple[str, ...]], list[FirmaKapsami]] = {}


def _anahtar(cfg: MikroConfig, kodlar: list[str]) -> tuple[str, str, tuple[str, ...]]:
    c = cfg.normalized()
    return (c.base_url, c.kullanici_kodu, tuple(kodlar))


def katalog(cfg: MikroConfig, *, yenile: bool = False) -> list[FirmaKapsami]:
    """
    Her firma kodunun kapsadığı yıl aralığını yoklar; okunamayan firma sessizce düşer.

    Erişilemeyen bir veritabanı yüzünden raporun tamamı düşmemeli — elde ne varsa
    onunla devam edilir, kalan yıllar zaten seçili firmadan okunur.
    """
    kodlar = firma_kodlari(cfg)
    if not kodlar:
        return []
    anahtar = _anahtar(cfg, kodlar)
    if not yenile and anahtar in _ONBELLEK:
        return _ONBELLEK[anahtar]

    out: list[FirmaKapsami] = []
    for kod in kodlar:
        try:
            ilk, son = fetch_yil_araligi(firma_client(cfg, kod))
        except MikroAPIError:
            continue
        kapsam = FirmaKapsami(firma_kodu=kod, ilk_yil=ilk, son_yil=son)
        if kapsam.gecerli:
            out.append(kapsam)
    _ONBELLEK[anahtar] = out
    return out


def onbellegi_temizle() -> None:
    """Ayarlar değişince çağrılır — eski kapsamlar yanlış veritabanına yönlendirmesin."""
    _ONBELLEK.clear()


def yil_icin_firma(kapsamlar: list[FirmaKapsami], yil: int) -> str:
    """
    Verilen yılı taşıyan firma kodu; bilinmiyorsa boş string.

    Birden fazla firma aynı yılı kapsıyorsa listedeki İLK sıradaki kazanır
    (kullanıcının yazdığı sıra). Devir yılında iki veritabanında da veri bulunur;
    hangisinin esas olduğunu kullanıcı sıralamayla söyler.
    """
    for k in kapsamlar:
        if k.icerir(yil):
            return k.firma_kodu
    return ""


def yillari_firmalara_dagit(kapsamlar: list[FirmaKapsami], yillar: list[int]) -> dict[int, str]:
    """Yıl → firma kodu eşlemesi; karşılığı olmayan yıl dışarıda kalır."""
    out: dict[int, str] = {}
    for y in yillar:
        kod = yil_icin_firma(kapsamlar, y)
        if kod:
            out[y] = kod
    return out
