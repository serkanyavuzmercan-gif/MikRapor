"""Reel değer ve finansman etkisi — karar destek amaçlı saf hesaplama motoru.

Nominal muhasebe tutarlarını değiştirmez. Açık alacak/borçların vadelerine göre bugünkü
ekonomik değerini ve kredi kartı borcunun kısmi ödenmesi hâlindeki finansman maliyetini
gösterir. Kullanılan oranlar senaryo varsayımıdır; resmî muhasebe/vergisel değer değildir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.ortak import csv_sayi
from domain.tahsilat_alacak import TahsilatAlacak


@dataclass
class ReelDegerVarsayim:
    yillik_iskonto_yuzde: float = 45.0
    kart_aylik_faiz_yuzde: float = 4.0
    kart_odeme_yuzde: float = 100.0
    kart_borcu_acik: float = 0.0
    kart_ufuk_ay: int = 12


@dataclass
class DegerOzet:
    nominal: float = 0.0
    bugunku_deger: float = 0.0
    vade_etkisi: float = 0.0
    agirlikli_gun: float = 0.0


@dataclass
class KartFinansmanAy:
    sira: int
    acilis_borc: float
    odeme: float
    finansman_maliyeti: float
    kapanis_borc: float


@dataclass
class KartFinansman:
    baslangic_borc: float = 0.0
    aylik_faiz_yuzde: float = 0.0
    odeme_yuzde: float = 0.0
    aylar: list[KartFinansmanAy] = field(default_factory=list)
    toplam_odeme: float = 0.0
    toplam_finansman_maliyeti: float = 0.0
    kalan_borc: float = 0.0

    @property
    def kapandi_mi(self) -> bool:
        return self.kalan_borc < 0.005


@dataclass
class ReelDegerAnalizi:
    varsayim: ReelDegerVarsayim = field(default_factory=ReelDegerVarsayim)
    alacak: DegerOzet = field(default_factory=DegerOzet)
    borc: DegerOzet = field(default_factory=DegerOzet)
    kart: KartFinansman = field(default_factory=KartFinansman)

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


def kart_finansmani_hesapla(v: ReelDegerVarsayim) -> KartFinansman:
    """Açık kart borcu için ödeme/finansman senaryosu.

    Ödeme oranı, ay başındaki borcun ödenen kısmıdır. Ödenmeyen kısım için aylık finansman
    maliyeti eklenir. %100 ödeme, borcu ilk ay tamamen kapatır ve maliyet doğurmaz.
    """
    kalan = max(0.0, v.kart_borcu_acik)
    odeme_orani = min(1.0, _oran(v.kart_odeme_yuzde))
    faiz_orani = _oran(v.kart_aylik_faiz_yuzde)
    kart = KartFinansman(
        baslangic_borc=kalan,
        aylik_faiz_yuzde=max(0.0, v.kart_aylik_faiz_yuzde),
        odeme_yuzde=min(100.0, max(0.0, v.kart_odeme_yuzde)),
    )
    for sira in range(1, max(1, int(v.kart_ufuk_ay)) + 1):
        if kalan < 0.005:
            break
        acilis = kalan
        odeme = min(acilis, acilis * odeme_orani)
        tasinan = acilis - odeme
        finansman = tasinan * faiz_orani
        kalan = tasinan + finansman
        kart.aylar.append(KartFinansmanAy(
            sira=sira,
            acilis_borc=acilis,
            odeme=odeme,
            finansman_maliyeti=finansman,
            kapanis_borc=kalan,
        ))
    kart.toplam_odeme = sum(a.odeme for a in kart.aylar)
    kart.toplam_finansman_maliyeti = sum(a.finansman_maliyeti for a in kart.aylar)
    kart.kalan_borc = kalan
    return kart


def build_reel_deger_analizi(ta: TahsilatAlacak, v: ReelDegerVarsayim) -> ReelDegerAnalizi:
    """Açık cari kalemler + kart borcundan reel değer/finansman analizini kurar."""
    parcalar = getattr(ta, "acik_vade_parcalari", []) or []
    return ReelDegerAnalizi(
        varsayim=v,
        alacak=_deger_ozeti(parcalar, "customer", v.yillik_iskonto_yuzde),
        borc=_deger_ozeti(parcalar, "supplier", v.yillik_iskonto_yuzde),
        kart=kart_finansmani_hesapla(v),
    )


def reel_deger_csv(a: ReelDegerAnalizi) -> str:
    """Reel değer analizini Türkçe Excel uyumlu CSV'ye çevirir."""
    s = csv_sayi
    v = a.varsayim
    out = ["Bölüm;Kalem;Değer"]
    out.extend([
        f"VARSAYIM;Yıllık iskonto / fırsat maliyeti %;{s(v.yillik_iskonto_yuzde)}",
        f"VARSAYIM;Kart aylık finansman maliyeti %;{s(v.kart_aylik_faiz_yuzde)}",
        f"VARSAYIM;Kart aylık ödeme oranı %;{s(v.kart_odeme_yuzde)}",
        f"ALACAK;Nominal;{s(a.alacak.nominal)}",
        f"ALACAK;Bugünkü ekonomik değer;{s(a.alacak.bugunku_deger)}",
        f"ALACAK;Vade maliyeti;{s(a.alacak.vade_etkisi)}",
        f"BORÇ;Nominal;{s(a.borc.nominal)}",
        f"BORÇ;Bugünkü ekonomik değer;{s(a.borc.bugunku_deger)}",
        f"BORÇ;Vade avantajı;{s(a.borc.vade_etkisi)}",
        f"NET;Nominal pozisyon;{s(a.nominal_net_pozisyon)}",
        f"NET;Reel pozisyon;{s(a.reel_net_pozisyon)}",
        f"NET;Vade etkisi;{s(a.net_vade_etkisi)}",
        f"KART;Başlangıç borcu;{s(a.kart.baslangic_borc)}",
        f"KART;Toplam finansman maliyeti;{s(a.kart.toplam_finansman_maliyeti)}",
        f"KART;Toplam ödeme;{s(a.kart.toplam_odeme)}",
        f"KART;Kalan borç;{s(a.kart.kalan_borc)}",
    ])
    out.append("KART TAKVİMİ;Ay;Açılış Borç;Ödeme;Finansman Maliyeti;Kapanış Borç")
    for ay in a.kart.aylar:
        out.append(
            f"KART TAKVİMİ;{ay.sira};{s(ay.acilis_borc)};{s(ay.odeme)};"
            f"{s(ay.finansman_maliyeti)};{s(ay.kapanis_borc)}"
        )
    return "\r\n".join(out)
