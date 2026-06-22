"""
Ay bazlı kâr/zarar (P&L) hesaplama motoru.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from fatura_analyzer import analyze_fatura_kar
from operational_analyzer import (
    GiderKalemi,
    IsletmeAnalizi,
    IsletmeParametreleri,
    PersonelGiderKalemi,
    analyze_operasyonel,
)
from parse_utils import format_tl
from parse_utils import extract_ana_hesap
from period_utils import filter_df_by_analiz_ayi

OPEX_ANA_HESAPLAR = {"730", "760", "770"}


@dataclass
class PersonelOzet:
    muavin_brut_ucret: float = 0.0
    muavin_sgk: float = 0.0
    harici_maas: float = 0.0
    gercek_personel_maliyeti: float = 0.0
    kalemler: list[PersonelGiderKalemi] = field(default_factory=list)


@dataclass
class KargoOzet:
    muavin_kargo: float = 0.0
    fatura_kargo: float = 0.0
    net_kargo_maliyeti: float = 0.0
    kaynak: str = ""


@dataclass
class MonthlyPLSonuc:
    analiz_ayi: str = ""
    brut_kar: float = 0.0
    toplam_operasyonel_gider: float = 0.0
    toplam_harici_maas: float = 0.0
    aylik_net_kar: float = 0.0
    muavin_gider_kalemleri: list[GiderKalemi] = field(default_factory=list)
    personel: PersonelOzet = field(default_factory=PersonelOzet)
    kargo: KargoOzet = field(default_factory=KargoOzet)
    isletme: IsletmeAnalizi | None = None
    fatura_kar: object | None = None
    yorumlar: list[str] = field(default_factory=list)


def aggregate_muavin_gider_kalemleri(muavin_df: pd.DataFrame) -> list[GiderKalemi]:
    """Muavin hareketlerinden 730/760/770 net gider kalemlerini üretir."""
    if muavin_df is None or muavin_df.empty:
        return []

    work = muavin_df.copy()
    work["ana_hesap"] = work["hesap_kodu"].apply(extract_ana_hesap)
    work = work[work["ana_hesap"].isin(OPEX_ANA_HESAPLAR)]

    if work.empty:
        return []

    grouped = (
        work.groupby(["hesap_kodu", "hesap_adi"], dropna=False)
        .agg(tl_borc=("tl_borc", "sum"), tl_alacak=("tl_alacak", "sum"))
        .reset_index()
    )
    kalemler: list[GiderKalemi] = []
    for _, row in grouped.iterrows():
        net = float(row["tl_borc"]) - float(row["tl_alacak"])
        if abs(net) < 0.01:
            continue
        kalemler.append(
            GiderKalemi(
                hesap_kodu=str(row["hesap_kodu"]),
                hesap_adi=str(row["hesap_adi"]),
                tutar=net,
            )
        )
    return sorted(kalemler, key=lambda k: k.hesap_kodu)


def analyze_monthly_pl(
    analiz_ayi: str,
    muavin_df: pd.DataFrame,
    alis_fatura_df: pd.DataFrame,
    satis_fatura_df: pd.DataFrame,
    maas_harici: float = 0.0,
    personel_maaslari: list | None = None,
    dukkan_metrekare: float = 0.0,
) -> MonthlyPLSonuc:
    """Seçilen ay için aylık P&L hesaplar."""
    muavin_ay = filter_df_by_analiz_ayi(muavin_df, "tarih", analiz_ayi)
    alis_ay = filter_df_by_analiz_ayi(alis_fatura_df, "tarih", analiz_ayi)
    satis_ay = filter_df_by_analiz_ayi(satis_fatura_df, "tarih", analiz_ayi)

    gider_kalemleri = aggregate_muavin_gider_kalemleri(muavin_ay)
    toplam_gider = sum(k.tutar for k in gider_kalemleri)

    fatura_kar = None
    brut_kar = 0.0
    if not alis_ay.empty or not satis_ay.empty:
        fatura_kar = analyze_fatura_kar(alis_ay, satis_ay)
        brut_kar = float(getattr(fatura_kar, "toplam_brut_kar", 0) or 0)

    params = IsletmeParametreleri(
        dukkan_metrekare=dukkan_metrekare,
        personel_maaslari=personel_maaslari or [],
    )
    isletme = analyze_operasyonel(
        gider_kalemleri,
        params,
        fatura_kar=fatura_kar,
        alis_fatura_df=alis_ay,
        satis_fatura_df=satis_ay,
    )

    harici = maas_harici if maas_harici else params.toplam_harici_maas
    personel = PersonelOzet(
        muavin_brut_ucret=isletme.brut_ucret_mizan,
        muavin_sgk=isletme.sgk_primi_mizan,
        harici_maas=harici,
        gercek_personel_maliyeti=isletme.brut_ucret_mizan
        + isletme.sgk_primi_mizan
        + harici,
        kalemler=isletme.personel_gider_kalemleri,
    )

    kargo_kaynak = "fatura" if isletme.kargo_gosterge_kaynak == "fatura" else "muavin"
    kargo = KargoOzet(
        muavin_kargo=isletme.kargo_gider_mizan,
        fatura_kargo=isletme.kargo_fatura_alis,
        net_kargo_maliyeti=isletme.kargo_gosterge_fatura,
        kaynak=kargo_kaynak,
    )

    aylik_net = brut_kar - toplam_gider - harici
    yorumlar = [
        f"Brüt kâr (fatura eşleşmesi): {format_tl(brut_kar)}.",
        f"Muavin operasyonel gider (730/760/770): {format_tl(toplam_gider)}.",
        f"Harici maaş: {format_tl(harici)}.",
        f"Aylık net kâr/zarar: {format_tl(aylik_net)}.",
    ]
    if isletme.yorum:
        yorumlar.append(isletme.yorum)

    return MonthlyPLSonuc(
        analiz_ayi=analiz_ayi,
        brut_kar=brut_kar,
        toplam_operasyonel_gider=toplam_gider,
        toplam_harici_maas=harici,
        aylik_net_kar=aylik_net,
        muavin_gider_kalemleri=gider_kalemleri,
        personel=personel,
        kargo=kargo,
        isletme=isletme,
        fatura_kar=fatura_kar,
        yorumlar=yorumlar,
    )
