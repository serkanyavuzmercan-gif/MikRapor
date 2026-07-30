"""
KDV nakit köprüsü — KDV bir gider değil, bir FİNANSMAN yüküdür.

100 TL'lik mal satıldığında 20 TL KDV aynı ay doğar ve ertesi ay beyanla devlete
ödenir. Ama o 100 TL müşteriden ortalama 90 günde tahsil edilir. Arada kalan sürede
KDV'yi firma kendi kesesinden finanse eder — nakit akışta bu, hiçbir kalemin altında
görünmeyen gerçek bir para bağıdır. Kullanıcının sorusu birebir buydu: «nakit akışta
mutlaka KDV olmalı».

Kaynak muhasebe yevmiyesidir:
  • 391 Hesaplanan KDV → satıştan doğan (alacak hareketleri)
  • 191 İndirilecek KDV → alıştan doğan (borç hareketleri)
Aradaki fark, o dönem devlete kalan nettir.

ORAN VARSAYILMAZ, ÖLÇÜLÜR. «KDV %20'dir» demek yanlış olurdu: firmanın ürün karması
%1, %10 ve %20'yi birlikte içerebilir, ihracat satışında KDV hiç doğmaz. Efektif oran
hesaplanan KDV'nin net satışa bölünmesiyle ölçülür (bkz. CLAUDE.md kural 6).

TARİH ARALIĞI: KDV hareketleri ve net satış AKIŞTIR, seçili aralıktan okunur; alacak
bakiyesi aralığın BİTİŞ gününün fotoğrafıdır. Aralık dışına çıkılmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from domain.ortak import csv_sayi
from domain.ortak import to_float as _f

# Bu hesaplar TDHP'de sabittir; kurulumdan kuruluma değişmez (kural 6 kapsamı dışı).
HESAPLANAN_HESAP = "391"    # satıştan doğan KDV
INDIRILECEK_HESAP = "191"   # alıştan doğan KDV

_SIFIR = 0.005


@dataclass
class AyKdv:
    """Bir ayın (YYYY-MM) KDV doğuşu — beyanı ertesi ay ödenir."""

    ay: str
    hesaplanan: float = 0.0
    indirilecek: float = 0.0

    @property
    def net(self) -> float:
        """Devlete kalan (eksi ise devreden KDV — o ay ödeme çıkmaz)."""
        return self.hesaplanan - self.indirilecek


@dataclass
class KdvKoprusu:
    """Dönemin KDV yükü ve alacağın içinde bağlı kalan KDV."""

    bas: str = ""
    bit: str = ""
    var: bool = False              # 191/391 muhasebeden okunabildi mi
    hesaplanan: float = 0.0
    indirilecek: float = 0.0
    net_satis: float = 0.0         # GL 60/61 — efektif oranı ÖLÇMEK için
    alacak: float = 0.0            # dönem sonu müşteri açık bakiyesi (KDV DÂHİL)
    aylik: list[AyKdv] = field(default_factory=list)

    @property
    def net_kdv(self) -> float:
        """Dönemde devlete kalan net KDV (eksi = devreden)."""
        return self.hesaplanan - self.indirilecek

    @property
    def olculdu(self) -> bool:
        """Efektif oran gerçekten ölçülebildi mi — ölçülemeyene rakam uydurulmaz."""
        return self.var and self.hesaplanan > _SIFIR and self.net_satis > _SIFIR

    @property
    def oran(self) -> float | None:
        """Ölçülen efektif KDV oranı (%). Varsayım değil, bu dönemin kendi rakamı."""
        return (self.hesaplanan / self.net_satis * 100.0) if self.olculdu else None

    @property
    def brut_satis(self) -> float | None:
        """Müşteriden istenen toplam — alacak da bu tutar üzerinden doğar."""
        return (self.net_satis + self.hesaplanan) if self.olculdu else None

    @property
    def alacaktaki_kdv(self) -> float | None:
        """
        Tahsil edilmemiş alacağın içindeki KDV.

        Alacak KDV DÂHİL doğar; bu tutarın KDV payı devlete çoktan beyan edilmiş,
        büyük kısmı ödenmiştir. Yani bu para dışarıda ve firmanın cebinden çıkmıştır.
        """
        oran = self.oran
        if oran is None or self.alacak <= _SIFIR:
            return None
        return self.alacak * oran / (100.0 + oran)

    @property
    def gun(self) -> int:
        """Seçili dönemin gün sayısı."""
        try:
            return (date.fromisoformat(self.bit) - date.fromisoformat(self.bas)).days + 1
        except ValueError:
            return 0

    @property
    def tahsil_gun(self) -> float | None:
        """
        Alacağın ortalama tahsil süresi (gün) — KDV kaç gün finanse ediliyor.

        Payda BRÜT satıştır: alacak KDV dâhil, net satışa bölmek süreyi şişirirdi.
        """
        brut = self.brut_satis
        if not brut or brut <= _SIFIR or self.gun <= 0 or self.alacak <= _SIFIR:
            return None
        return self.alacak / (brut / self.gun)

    @property
    def aylik_ortalama_net(self) -> float | None:
        """Ayda ortalama ne kadar KDV çıkıyor — nakit planı için."""
        dolu = [a for a in self.aylik if abs(a.net) > _SIFIR]
        return (sum(a.net for a in dolu) / len(dolu)) if dolu else None

    @property
    def sebep(self) -> str:
        """Rakam gösterilemiyorsa NEDEN gösterilemediği — boş hücre açıklamasız kalmaz."""
        if not self.var:
            return "KDV hesapları (191/391) muhasebeden okunamadı."
        if self.hesaplanan <= _SIFIR:
            return ("Bu dönemde 391 Hesaplanan KDV hesabına hareket girmemiş; "
                    "satışın KDV'si muhasebeye başka bir hesaptan işleniyor olabilir.")
        if self.net_satis <= _SIFIR:
            return "Dönemde net satış (60/61) bulunamadı; efektif KDV oranı ölçülemedi."
        return ""


def build_kdv_koprusu(
    rows: list[dict] | None = None,
    *,
    net_satis: float = 0.0,
    alacak: float = 0.0,
    bas: str = "",
    bit: str = "",
) -> KdvKoprusu:
    """
    fetch_kdv_ozet satırlarından KDV köprüsünü kurar.

    Satır şekli: {'ay': 'YYYY-MM', 'hesap': '191'|'391', 'borc': x, 'alacak': y}.
    191 BORÇ tarafından (alıştan indirilecek), 391 ALACAK tarafından (satıştan
    hesaplanan) okunur — ay sonu mahsup fişi bu iki tarafa dokunmaz, o yüzden
    mükerrer saymaz.
    """
    k = KdvKoprusu(bas=bas, bit=bit, net_satis=net_satis, alacak=alacak,
                   var=rows is not None)
    aylar: dict[str, AyKdv] = {}
    for r in (rows or []):
        hesap = str(r.get("hesap", r.get("HESAP")) or "").strip()
        ay = str(r.get("ay", r.get("AY")) or "")
        borc = _f(r.get("borc", r.get("BORC")))
        alacak_h = _f(r.get("alacak", r.get("ALACAK")))
        a = aylar.get(ay)
        if a is None:
            a = aylar[ay] = AyKdv(ay=ay)
        if hesap == HESAPLANAN_HESAP:
            a.hesaplanan += alacak_h
        elif hesap == INDIRILECEK_HESAP:
            a.indirilecek += borc
    k.aylik = [aylar[key] for key in sorted(aylar)]
    k.hesaplanan = sum(a.hesaplanan for a in k.aylik)
    k.indirilecek = sum(a.indirilecek for a in k.aylik)
    return k


def kdv_csv(k: KdvKoprusu) -> str:
    """KDV köprüsünü CSV'ye çevirir (Nakit Akış CSV'sinin sonuna eklenir)."""
    if not k.var:
        return ""
    s = csv_sayi
    out = ["Bölüm;Kalem;Tutar (TL)"]
    out.append(f"KDV;Hesaplanan KDV (391 — satıştan);{s(k.hesaplanan)}")
    out.append(f"KDV;İndirilecek KDV (191 — alıştan);{s(k.indirilecek)}")
    out.append(f"KDV;Devlete kalan net KDV;{s(k.net_kdv)}")
    if k.oran is not None:
        out.append(f"KDV;Ölçülen efektif KDV oranı (%);{s(k.oran)}")
    if k.alacaktaki_kdv is not None:
        out.append(f"KDV;Tahsil edilmemiş alacaktaki KDV;{s(k.alacaktaki_kdv)}")
    if k.tahsil_gun is not None:
        out.append(f"KDV;Alacağın ortalama tahsil süresi (gün);{s(k.tahsil_gun)}")
    if k.sebep:
        out.append(f"KDV;Not;{k.sebep}")
    for a in k.aylik:
        out.append(f"KDV AYLIK;{a.ay} hesaplanan;{s(a.hesaplanan)}")
        out.append(f"KDV AYLIK;{a.ay} indirilecek;{s(a.indirilecek)}")
        out.append(f"KDV AYLIK;{a.ay} net;{s(a.net)}")
    return "\r\n".join(out)
