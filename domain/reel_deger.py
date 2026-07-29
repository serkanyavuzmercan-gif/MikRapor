"""
Vade etkisi — karar destek amaçlı saf hesaplama motoru.

TEK SORUYU CEVAPLAR: vadeli satmak neye mal oluyor, vadeli almak ne kazandırıyor?
Açık alacak/borçların vadelerine göre bugünkü ekonomik değerini hesaplar; nominal
muhasebe tutarlarını değiştirmez. Kullanılan oran senaryo varsayımıdır, resmî
muhasebe/vergisel değer değildir.

Kredi kartı finansman senaryosu BURADAN ÇIKARILDI (Tahmin & Projeksiyon'a taşındı):
sekmedeki dört değişkenin üçü yalnız en alttaki kart tablosunu besliyordu, panel bunu
söylemiyordu ve aynı kart borcu iki sekmede birden görünüyordu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.ortak import csv_sayi
from domain.tahsilat_alacak import TahsilatAlacak


@dataclass
class ReelDegerVarsayim:
    # TEK DEĞİŞKEN. Kredi kartı senaryosu Tahmin & Projeksiyon'a taşındı: bu sekmedeki
    # dört değişkenin ÜÇÜ yalnız en alttaki kart tablosunu besliyordu ve panel bunu
    # hiçbir yerde söylemiyordu. Sekme artık tek soruyu cevaplıyor: vadeli satmak neye
    # mal oluyor, vadeli almak ne kazandırıyor.
    yillik_iskonto_yuzde: float = 45.0


@dataclass
class DegerOzet:
    nominal: float = 0.0
    bugunku_deger: float = 0.0
    vade_etkisi: float = 0.0
    agirlikli_gun: float = 0.0


@dataclass
class ReelDegerAnalizi:
    varsayim: ReelDegerVarsayim = field(default_factory=ReelDegerVarsayim)
    alacak: DegerOzet = field(default_factory=DegerOzet)
    borc: DegerOzet = field(default_factory=DegerOzet)

    @property
    def nominal_net_pozisyon(self) -> float:
        return self.alacak.nominal - self.borc.nominal

    @property
    def reel_net_pozisyon(self) -> float:
        return self.alacak.bugunku_deger - self.borc.bugunku_deger

    @property
    def net_vade_etkisi(self) -> float:
        """Vade nedeniyle net ekonomik pozisyondaki değişim (reel − nominal)."""
        return self.reel_net_pozisyon - self.nominal_net_pozisyon


def _oran(yuzde: float) -> float:
    return max(0.0, float(yuzde)) / 100.0


def bugunku_deger(tutar: float, gun: float, yillik_iskonto_yuzde: float) -> float:
    """Gelecekteki nominal tutarın bugünkü değeri (bileşik yıllık iskonto)."""
    nominal = max(0.0, float(tutar))
    if nominal < 0.005:
        return 0.0
    gun = max(0.0, float(gun))
    oran = _oran(yillik_iskonto_yuzde)
    if gun < 0.005 or oran < 0.0000001:
        return nominal
    return nominal / ((1.0 + oran) ** (gun / 365.0))


def _deger_ozeti(parcalar: list, sinif: str, yillik_iskonto_yuzde: float) -> DegerOzet:
    ilgili = [p for p in parcalar if getattr(p, "sinif", "") == sinif and p.tutar > 0.005]
    nominal = sum(p.tutar for p in ilgili)
    if nominal < 0.005:
        return DegerOzet()
    pv = sum(bugunku_deger(p.tutar, p.vade_gun, yillik_iskonto_yuzde) for p in ilgili)
    agirlikli_gun = sum(max(0, p.vade_gun) * p.tutar for p in ilgili) / nominal
    return DegerOzet(
        nominal=nominal,
        bugunku_deger=pv,
        vade_etkisi=nominal - pv,
        agirlikli_gun=agirlikli_gun,
    )


def build_reel_deger_analizi(ta: TahsilatAlacak, v: ReelDegerVarsayim) -> ReelDegerAnalizi:
    """Açık cari kalemlerden vade etkisi analizini kurar."""
    parcalar = getattr(ta, "acik_vade_parcalari", []) or []
    return ReelDegerAnalizi(
        varsayim=v,
        alacak=_deger_ozeti(parcalar, "customer", v.yillik_iskonto_yuzde),
        borc=_deger_ozeti(parcalar, "supplier", v.yillik_iskonto_yuzde),
    )


def reel_deger_csv(a: ReelDegerAnalizi) -> str:
    """Vade etkisi analizini Türkçe Excel uyumlu CSV'ye çevirir."""
    s = csv_sayi
    v = a.varsayim
    out = ["Bölüm;Kalem;Değer"]
    out.extend([
        f"VARSAYIM;Paranın yıllık maliyeti %;{s(v.yillik_iskonto_yuzde)}",
        f"ALACAK;Nominal;{s(a.alacak.nominal)}",
        f"ALACAK;Bugünkü ekonomik değer;{s(a.alacak.bugunku_deger)}",
        f"ALACAK;Vade maliyeti;{s(a.alacak.vade_etkisi)}",
        f"BORÇ;Nominal;{s(a.borc.nominal)}",
        f"BORÇ;Bugünkü ekonomik değer;{s(a.borc.bugunku_deger)}",
        f"BORÇ;Vade avantajı;{s(a.borc.vade_etkisi)}",
        f"NET;Nominal pozisyon;{s(a.nominal_net_pozisyon)}",
        f"NET;Reel pozisyon;{s(a.reel_net_pozisyon)}",
        f"NET;Vade etkisi;{s(a.net_vade_etkisi)}",
    ])
    return "\r\n".join(out)
