"""
Tahmin motoru — geleceğe dönük ciro / brüt kâr / net kâr / nakit projeksiyonu.

Hibrit: varsayımlar (baz ciro, aylık büyüme %, brüt marj %, sabit gider) geçmiş veriden otomatik
önerilir (oner_varsayim) ama kullanıcı düzenleyip senaryo değiştirebilir. build_tahmin saf bir
fonksiyondur (Mikro'ya gitmez) → kullanıcı her oynadığında anında yeniden hesaplanır.

Model (aylık, n = 1..ufuk):
  ciro_n      = baz_ciro × (1 + büyüme)^n
  brüt_kâr_n  = ciro_n × marj
  net_kâr_n   = brüt_kâr_n − sabit_gider
  nakit_n     = nakit_(n-1) + net_kâr_n      (basit: kâr nakde döner; tahsilat gecikmesi yok)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortak import csv_sayi


def _ay_ekle(yyyymm: str, k: int) -> str:
    """'2026-06' + k ay → 'YYYY-MM'."""
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
    except (ValueError, IndexError):
        return ""
    idx = y * 12 + (m - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def aylik_buyume_oner(seri: list[float], alt: float = -15.0, ust: float = 20.0) -> float:
    """Aylık seriden bileşik aylık büyüme (%) önerir, [alt, ust] aralığına kırpar."""
    vals = [v for v in seri if v and v > 0]
    if len(vals) < 2:
        return 0.0
    n = len(vals) - 1
    oran = (vals[-1] / vals[0]) ** (1.0 / n) - 1.0
    return max(alt, min(ust, oran * 100.0))


@dataclass
class TahminVarsayim:
    baslangic_ay: str = ""        # 'YYYY-MM' — projeksiyon bunun ERTESİ ayından başlar
    baslangic_nakit: float = 0.0
    baz_ciro: float = 0.0         # aylık ciro tabanı (1. tahmin ayı)
    buyume_yuzde: float = 0.0     # aylık büyüme %
    marj_yuzde: float = 0.0       # brüt marj %
    sabit_gider: float = 0.0      # aylık sabit/işletme gideri
    ufuk_ay: int = 12

    def ozet(self) -> str:
        return (f"baz ciro {self.baz_ciro:,.0f} · büyüme %{self.buyume_yuzde:.1f}/ay · "
                f"marj %{self.marj_yuzde:.1f} · sabit gider {self.sabit_gider:,.0f}").replace(",", ".")


@dataclass
class AyTahmin:
    ay: str
    ciro: float = 0.0
    brut_kar: float = 0.0
    sabit_gider: float = 0.0
    net_kar: float = 0.0
    nakit: float = 0.0


@dataclass
class Tahmin:
    varsayim: TahminVarsayim = field(default_factory=TahminVarsayim)
    aylar: list = field(default_factory=list)
    toplam_ciro: float = 0.0
    toplam_brut: float = 0.0
    toplam_net: float = 0.0
    son_nakit: float = 0.0
    en_dusuk_nakit: float = 0.0
    en_dusuk_ay: str = ""


def build_tahmin(v: TahminVarsayim) -> Tahmin:
    """Varsayımlardan aylık projeksiyon üretir (saf fonksiyon)."""
    t = Tahmin(varsayim=v)
    g = v.buyume_yuzde / 100.0
    marj = v.marj_yuzde / 100.0
    nakit = v.baslangic_nakit
    en_dusuk = nakit
    en_dusuk_ay = v.baslangic_ay
    for n in range(1, max(0, v.ufuk_ay) + 1):
        ciro = v.baz_ciro * ((1.0 + g) ** n)
        brut = ciro * marj
        net = brut - v.sabit_gider
        nakit += net
        ay = _ay_ekle(v.baslangic_ay, n)
        t.aylar.append(AyTahmin(ay=ay, ciro=ciro, brut_kar=brut,
                                sabit_gider=v.sabit_gider, net_kar=net, nakit=nakit))
        if nakit < en_dusuk:
            en_dusuk, en_dusuk_ay = nakit, ay
    t.toplam_ciro = sum(a.ciro for a in t.aylar)
    t.toplam_brut = sum(a.brut_kar for a in t.aylar)
    t.toplam_net = sum(a.net_kar for a in t.aylar)
    t.son_nakit = t.aylar[-1].nakit if t.aylar else v.baslangic_nakit
    t.en_dusuk_nakit = en_dusuk
    t.en_dusuk_ay = en_dusuk_ay
    return t


def oner_varsayim(
    *,
    satis_serisi: list[float],
    brut_marj_yuzde: float,
    baslangic_nakit: float,
    aylik_sabit_gider: float,
    baslangic_ay: str,
    ufuk_ay: int = 12,
) -> TahminVarsayim:
    """Geçmiş aylık satış serisi + marj + nakit + gideri varsayım taslağına çevirir."""
    pozitif = [v for v in satis_serisi if v and v > 0]
    if pozitif:
        # Baz ciro: son 3 ayın ortalaması (yoksa tüm ortalama)
        son = pozitif[-3:] if len(pozitif) >= 3 else pozitif
        baz = sum(son) / len(son)
    else:
        baz = 0.0
    return TahminVarsayim(
        baslangic_ay=baslangic_ay,
        baslangic_nakit=baslangic_nakit,
        baz_ciro=baz,
        buyume_yuzde=aylik_buyume_oner(satis_serisi),
        marj_yuzde=brut_marj_yuzde,
        sabit_gider=max(0.0, aylik_sabit_gider),
        ufuk_ay=ufuk_ay,
    )


def tahmin_csv(t: Tahmin) -> str:
    """Tahmin projeksiyonunu CSV'ye çevirir (; ayraç, Türkçe ondalık)."""
    s = csv_sayi

    v = t.varsayim
    out = ["Bölüm;Kalem;Değer"]
    out.append(f"VARSAYIM;Başlangıç Nakit;{s(v.baslangic_nakit)}")
    out.append(f"VARSAYIM;Baz Aylık Ciro;{s(v.baz_ciro)}")
    out.append(f"VARSAYIM;Aylık Büyüme %;{s(v.buyume_yuzde)}")
    out.append(f"VARSAYIM;Brüt Marj %;{s(v.marj_yuzde)}")
    out.append(f"VARSAYIM;Aylık Sabit Gider;{s(v.sabit_gider)}")
    out.append("PROJEKSİYON;Ay;Ciro;Brüt Kâr;Net Kâr;Nakit")
    for a in t.aylar:
        out.append(f"AY;{a.ay};{s(a.ciro)};{s(a.brut_kar)};{s(a.net_kar)};{s(a.nakit)}")
    out.append(f"TOPLAM;Ciro;{s(t.toplam_ciro)}")
    out.append(f"TOPLAM;Brüt Kâr;{s(t.toplam_brut)}")
    out.append(f"TOPLAM;Net Kâr;{s(t.toplam_net)}")
    out.append(f"TOPLAM;Dönem Sonu Nakit;{s(t.son_nakit)}")
    out.append(f"TOPLAM;En Düşük Nakit ({t.en_dusuk_ay});{s(t.en_dusuk_nakit)}")
    return "\r\n".join(out)
