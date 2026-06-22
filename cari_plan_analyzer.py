"""
120 tahsilat ve 320 tediye plan analizi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from parse_utils import format_tl


@dataclass
class CariPlanHesap:
    hesap_kodu: str
    hesap_adi: str
    acik_bakiye: float
    vadesi_gecen: float
    vadesi_gelmeyen: float


@dataclass
class CariPlanSonuc:
    plan_turu: str = ""
    baslik: str = ""
    rapor_referans_tarihi: str = ""
    toplam_acik: float = 0.0
    vadesi_gecen: float = 0.0
    vadesi_gelmeyen: float = 0.0
    hesap_sayisi: int = 0
    top_hesaplar: list[CariPlanHesap] = field(default_factory=list)


def analyze_cari_plan(df: pd.DataFrame) -> CariPlanSonuc:
    """120 tahsilat veya 320 tediye plan dosyasını analiz eder."""
    if df is None or df.empty:
        return CariPlanSonuc()

    plan_turu = str(df["plan_turu"].iloc[0]) if "plan_turu" in df.columns else "tahsilat"
    baslik = "120 Tahsilat Planı" if plan_turu == "tahsilat" else "320 Ödeme Planı (Tediye)"
    ref_date = str(df["rapor_referans_tarihi"].iloc[0]) if "rapor_referans_tarihi" in df.columns else ""

    overdue_mask = df["vade_kalan_gun"] < 0
    vadesi_gecen = float(df.loc[overdue_mask, "meblag"].abs().sum())
    vadesi_gelmeyen = float(df.loc[~overdue_mask, "meblag"].abs().sum())

    hesaplar: list[CariPlanHesap] = []
    for hesap_kodu, group in df.groupby("hesap_kodu", sort=False):
        hesap_adi = str(group["hesap_adi"].iloc[0])
        acik_bakiye = abs(float(group["satir_bakiye"].iloc[-1]))
        gecen = float(group.loc[group["vade_kalan_gun"] < 0, "meblag"].abs().sum())
        gelmeyen = float(group.loc[group["vade_kalan_gun"] >= 0, "meblag"].abs().sum())
        hesaplar.append(
            CariPlanHesap(
                hesap_kodu=hesap_kodu,
                hesap_adi=hesap_adi,
                acik_bakiye=acik_bakiye,
                vadesi_gecen=gecen,
                vadesi_gelmeyen=gelmeyen,
            )
        )

    toplam_acik = sum(h.acik_bakiye for h in hesaplar)
    top = sorted(hesaplar, key=lambda h: h.acik_bakiye, reverse=True)[:10]

    return CariPlanSonuc(
        plan_turu=plan_turu,
        baslik=baslik,
        rapor_referans_tarihi=ref_date,
        toplam_acik=toplam_acik,
        vadesi_gecen=vadesi_gecen,
        vadesi_gelmeyen=vadesi_gelmeyen,
        hesap_sayisi=len(hesaplar),
        top_hesaplar=top,
    )


def compute_vade_net(
    tahsilat: CariPlanSonuc | None,
    tediye: CariPlanSonuc | None,
) -> float | None:
    """Vadesi gelmeyen tahsilat − vadesi gelmeyen ödeme."""
    if tahsilat is None or tediye is None:
        return None
    if not tahsilat.hesap_sayisi and not tediye.hesap_sayisi:
        return None
    return tahsilat.vadesi_gelmeyen - tediye.vadesi_gelmeyen


def plan_ozet_metin(
    tahsilat: CariPlanSonuc | None,
    tediye: CariPlanSonuc | None,
) -> list[str]:
    lines: list[str] = []
    if tahsilat and tahsilat.hesap_sayisi:
        lines.append(
            f"Tahsilat planı: açık {format_tl(tahsilat.toplam_acik)}, "
            f"vadesi geçen {format_tl(tahsilat.vadesi_gecen)}, "
            f"vadesi gelmeyen {format_tl(tahsilat.vadesi_gelmeyen)} "
            f"({tahsilat.hesap_sayisi} cari)."
        )
    if tediye and tediye.hesap_sayisi:
        lines.append(
            f"Ödeme planı: açık {format_tl(tediye.toplam_acik)}, "
            f"vadesi geçen {format_tl(tediye.vadesi_gecen)}, "
            f"vadesi gelmeyen {format_tl(tediye.vadesi_gelmeyen)} "
            f"({tediye.hesap_sayisi} cari)."
        )
    vade_net = compute_vade_net(tahsilat, tediye)
    if vade_net is not None:
        lines.append(f"Vade neti (gelmeyen tahsilat − gelmeyen ödeme): {format_tl(vade_net)}.")
    return lines
