"""
Ay bazlı analiz veri modelleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from operational_analyzer import PersonelMaas


@dataclass
class AylikMaasGirisi:
    analiz_ayi: str
    personel_maaslari: list[PersonelMaas] = field(default_factory=list)

    @property
    def toplam_resmi_maas(self) -> float:
        return sum(p.resmi_maas for p in self.personel_maaslari)

    @property
    def toplam_harici_maas(self) -> float:
        return sum(p.harici_maas for p in self.personel_maaslari)

    @property
    def toplam_maas(self) -> float:
        return sum(p.toplam for p in self.personel_maaslari)

    @property
    def personel_sayisi(self) -> int:
        return len(self.personel_maaslari)


@dataclass
class AnalizVeriSeti:
    analiz_ayi: str
    muavin_df: pd.DataFrame
    alis_fatura_df: pd.DataFrame
    satis_fatura_df: pd.DataFrame
    banka_df: pd.DataFrame
    maas: AylikMaasGirisi
    dukkan_metrekare: float = 0.0
    muavin_path: str = ""
    alis_fatura_path: str = ""
    satis_fatura_path: str = ""
    banka_paths: list[str] = field(default_factory=list)
    tahsilat_plan_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    tediye_plan_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    tahsilat_plan_path: str = ""
    tediye_plan_path: str = ""

    @property
    def has_muavin(self) -> bool:
        return self.muavin_df is not None and not self.muavin_df.empty

    @property
    def has_fatura(self) -> bool:
        return (
            (self.alis_fatura_df is not None and not self.alis_fatura_df.empty)
            or (self.satis_fatura_df is not None and not self.satis_fatura_df.empty)
        )

    @property
    def has_banka(self) -> bool:
        return self.banka_df is not None and not self.banka_df.empty

    @property
    def has_tahsilat_plan(self) -> bool:
        return self.tahsilat_plan_df is not None and not self.tahsilat_plan_df.empty

    @property
    def has_tediye_plan(self) -> bool:
        return self.tediye_plan_df is not None and not self.tediye_plan_df.empty

    @property
    def has_veri(self) -> bool:
        return (
            self.has_muavin
            or self.has_fatura
            or self.has_banka
            or self.has_tahsilat_plan
            or self.has_tediye_plan
        )
