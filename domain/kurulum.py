"""
Kurulum tanıma — «bu Mikro kurulumu nasıl çalışıyor?»

NEDEN VAR. MikRapor'un hesaplama kuralları (satış irsaliyeden mi faturadan mı sayılsın,
alışta hangisi) şimdiye kadar ELLE seçiliyordu ve varsayılanlar tek bir firmanın iş
akışına göreydi. Bu, program başka bir Mikro kurulumunda ilk açıldığında sessizce
yanlış rakam göstermesi demek — üstelik fark küçük değil: aynı veride «Satış: İrsaliye
+ Fatura» 20.481.407 TL derken «Yalnız Fatura» 1.095.172 TL diyor. On dokuz kat.

Ayarı varsaymak yerine ÖLÇÜYORUZ. Ölçüm bu oturumda teşhis betikleri olarak yazılmıştı;
burada karar veren saf mantığa dönüşüyor.

İKİ SORU, İKİ ÖLÇÜM:

1. Faturalaşma AYRI bir stok hareketi mi yaratıyor?
   • Damgalama modeli — irsaliye satırı `sth_fat_uid` ile damgalanır, fatura satırı
     yaratılmaz. İrsaliye + fatura toplanabilir (canlıda 17.430 damgalı irsaliyeye
     karşı 262 fatura satırı).
   • Kopyalama modeli — faturalaşınca ikinci satır doğar. Toplamak iki kat şişirir;
     yalnız fatura sayılmalı.

2. Mal hangi kapıdan giriyor?
   Mikro'da evraktip 12'nin adı «alış irsaliyesi / DEPO GİRİŞİ»: aynı kod hem dışarıdan
   gelen malı hem depolar arası nakli taşır. Girişlerin hepsinin çıkış deposu doluysa o
   kod tamamen iç nakildir; alınan mal doğrudan faturayla giriyordur.

EMİN OLAMAZSAK KARIŞMIYORUZ. Ölçüm zayıfsa (veri yok, desen belirsiz) mevcut ayar
korunur ve gerekçesi «emin olamadım» diye yazılır. Yanlış bir otomatik ayar, elle
seçilmiş bir ayardan daha zararlıdır: kullanıcı onu kendi seçmediği için sorgulamaz.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.ortak import to_float as _f

# Fatura satırı, damgalı irsaliye satırının bu oranından azsa damgalama modelidir.
# Canlıda 262/17.430 = %1,5; kopyalama modelinde bu oran 1'e yaklaşır.
_DAMGA_ESIGI = 0.5

# Girişlerin bu yüzdesinden azı dışarıdan geliyorsa evraktip tamamen iç nakildir.
_DISARIDAN_ESIGI = 1.0

# Bunun altında hareket varsa desen okunamaz — karar verilmez, mevcut ayar korunur.
_ASGARI_SATIR = 50

KESIN = "kesin"
ZAYIF = "zayif"


@dataclass
class Tespit:
    """Tek bir ayar için ölçüm sonucu."""

    alan: str            # "satis_bazi" | "alis_bazi"
    deger: str           # önerilen ayar kodu
    guven: str           # KESIN | ZAYIF
    gerekce: str         # kullanıcıya gösterilecek tek cümle

    @property
    def uygulanabilir(self) -> bool:
        return self.guven == KESIN


@dataclass
class KurulumTespiti:
    tespitler: list[Tespit]

    def deger(self, alan: str) -> str | None:
        t = next((x for x in self.tespitler if x.alan == alan and x.uygulanabilir), None)
        return t.deger if t else None

    @property
    def kesin_sayisi(self) -> int:
        return sum(1 for t in self.tespitler if t.uygulanabilir)

    def ozet(self) -> str:
        if not self.tespitler:
            return "Kurulum okunamadı — ayarlar olduğu gibi bırakıldı."
        if not self.kesin_sayisi:
            return "Desen net değil — ayarlar olduğu gibi bırakıldı."
        return f"{self.kesin_sayisi} ayar ölçümle belirlendi."


def _topla(rows: list[dict], tip: int) -> dict[tuple[int, int], list[float]]:
    """(evraktip, damgalı mı) → [satır, tutar]."""
    out: dict[tuple[int, int], list[float]] = {}
    for r in rows or []:
        if int(_f(r.get("sth_tip", r.get("STH_TIP")))) != tip:
            continue
        anahtar = (int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP")))),
                   int(_f(r.get("faturalandi", r.get("FATURALANDI")))))
        t = out.setdefault(anahtar, [0.0, 0.0])
        t[0] += _f(r.get("adet", r.get("ADET")))
        t[1] += _f(r.get("tutar", r.get("TUTAR")))
    return out


def _satis_bazi(rows: list[dict]) -> Tespit:
    kova = _topla(rows, 1)
    damgali = kova.get((1, 1), [0.0, 0.0])           # faturalanmış satış irsaliyesi
    bekleyen = kova.get((1, 0), [0.0, 0.0])
    fatura = [sum(v[0] for (ev, _), v in kova.items() if ev == 4),
              sum(v[1] for (ev, _), v in kova.items() if ev == 4)]
    toplam_satir = damgali[0] + bekleyen[0] + fatura[0]

    if toplam_satir < _ASGARI_SATIR:
        return Tespit("satis_bazi", "sevk", ZAYIF,
                      "Dönemde desen okunacak kadar satış hareketi yok.")
    if damgali[0] < 1:
        return Tespit("satis_bazi", "sevk", ZAYIF,
                      "Faturalanmış irsaliye yok — faturalaşma modeli ölçülemedi.")
    if fatura[0] < damgali[0] * _DAMGA_ESIGI:
        return Tespit(
            "satis_bazi", "sevk", KESIN,
            f"Faturalaşma kopya satır yaratmıyor ({int(damgali[0]):,} damgalı irsaliyeye "
            f"karşı {int(fatura[0]):,} fatura satırı), irsaliye + fatura toplanabilir."
            .replace(",", "."))
    return Tespit(
        "satis_bazi", "fatura", KESIN,
        f"Faturalaşınca ikinci satır doğuyor ({int(damgali[0]):,} damgalı irsaliyeye "
        f"karşı {int(fatura[0]):,} fatura satırı); toplamak satışı iki kat şişirirdi."
        .replace(",", "."))


def _alis_bazi(rows: list[dict], depo_rows: list[dict]) -> Tespit:
    kova = _topla(rows, 0)
    damgali = kova.get((12, 1), [0.0, 0.0])
    bekleyen = kova.get((12, 0), [0.0, 0.0])
    fatura = [sum(v[0] for (ev, _), v in kova.items() if ev == 3),
              sum(v[1] for (ev, _), v in kova.items() if ev == 3)]
    irs_satir = damgali[0] + bekleyen[0]

    if irs_satir + fatura[0] < _ASGARI_SATIR:
        return Tespit("alis_bazi", "fatura", ZAYIF,
                      "Dönemde desen okunacak kadar alış hareketi yok.")
    if irs_satir < 1:
        return Tespit("alis_bazi", "fatura", KESIN,
                      "Alış irsaliyesi hiç kullanılmıyor; mal doğrudan faturayla giriyor.")

    # Depo kırılımı: dışarıdan gelen malın çıkış deposu yoktur, transferde iki depo dolu.
    dis = ic = 0.0
    for r in depo_rows or []:
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if int(_f(r.get("transfer", r.get("TRANSFER")))):
            ic += tutar
        else:
            dis += tutar
    toplam = dis + ic
    if toplam > 0.005 and dis / toplam * 100 <= _DISARIDAN_ESIGI:
        return Tespit(
            "alis_bazi", "fatura", KESIN,
            "«Alış irsaliyesi» görünen hareketlerin tamamı depolar arası nakil "
            "(hiçbirinin çıkış deposu boş değil); alınan mal doğrudan faturayla giriyor.")
    if not depo_rows:
        return Tespit("alis_bazi", "fatura", ZAYIF,
                      "Depo kırılımı okunamadı — alış irsaliyesi gerçek mal mı ayırt edilemedi.")
    if damgali[0] >= 1 and fatura[0] < damgali[0] * _DAMGA_ESIGI:
        return Tespit(
            "alis_bazi", "irsaliye", KESIN,
            "Alışta faturalaşma kopya satır yaratmıyor ve mal irsaliyeyle giriyor; "
            "depoya giren malın tamamı irsaliye tutarıdır.")
    return Tespit("alis_bazi", "fatura", ZAYIF,
                  "Alış deseni net değil — güvenli olan yalnız faturayı saymak.")


def kurulumu_tespit_et(
    faturalasma_rows: list[dict] | None = None,
    depo_rows: list[dict] | None = None,
) -> KurulumTespiti:
    """Çekilmiş ölçüm satırlarından hesaplama kurallarını belirler (saf)."""
    if faturalasma_rows is None:
        return KurulumTespiti([])
    return KurulumTespiti([
        _satis_bazi(faturalasma_rows),
        _alis_bazi(faturalasma_rows, depo_rows or []),
    ])
