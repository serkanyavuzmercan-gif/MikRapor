"""
Önceki ay ile kıyaslama (trend) analizi.
"""

from __future__ import annotations

from dataclasses import dataclass

from cashflow_analyzer import analyze_nakit_akis
from models import AnalizVeriSeti
from monthly_pl_analyzer import analyze_monthly_pl
from parse_utils import format_tl
from period_utils import analiz_ayi_label, filter_df_by_analiz_ayi, previous_analiz_ayi


@dataclass
class AyKarsilastirma:
    onceki_ayi: str
    net_kar: float
    net_kar_onceki: float
    net_kar_fark: float
    brut_kar: float
    brut_kar_onceki: float
    brut_kar_fark: float
    gider: float
    gider_onceki: float
    gider_fark: float
    nakit_sonu: float
    nakit_sonu_onceki: float
    nakit_sonu_fark: float
    yorum: str = ""


def veri_has_ay(veri: AnalizVeriSeti, ayi: str) -> bool:
    """Veri setinde belirtilen ay için en az bir kayıt var mı."""
    checks = [
        (veri.muavin_df, "tarih"),
        (veri.banka_df, "tarih"),
        (veri.alis_fatura_df, "tarih"),
        (veri.satis_fatura_df, "tarih"),
    ]
    for df, col in checks:
        if df is not None and not df.empty:
            if not filter_df_by_analiz_ayi(df, col, ayi).empty:
                return True
    return False


def _pct_change(current: float, previous: float) -> str:
    if abs(previous) < 1:
        if abs(current) < 1:
            return "—"
        return "yeni"
    pct = (current - previous) / abs(previous) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _ozet_satirlari(k: AyKarsilastirma) -> list[str]:
    onceki_label = analiz_ayi_label(k.onceki_ayi)
    return [
        f"Net kâr/zarar: {format_tl(k.net_kar)} (önceki: {format_tl(k.net_kar_onceki)}, "
        f"fark {format_tl(k.net_kar_fark)}, {_pct_change(k.net_kar, k.net_kar_onceki)})",
        f"Brüt kâr: {format_tl(k.brut_kar)} (önceki: {format_tl(k.brut_kar_onceki)}, "
        f"fark {format_tl(k.brut_kar_fark)}, {_pct_change(k.brut_kar, k.brut_kar_onceki)})",
        f"Operasyonel gider: {format_tl(k.gider)} (önceki: {format_tl(k.gider_onceki)}, "
        f"fark {format_tl(k.gider_fark)}, {_pct_change(k.gider, k.gider_onceki)})",
        f"Dönem sonu nakit: {format_tl(k.nakit_sonu)} (önceki: {format_tl(k.nakit_sonu_onceki)}, "
        f"fark {format_tl(k.nakit_sonu_fark)}, {_pct_change(k.nakit_sonu, k.nakit_sonu_onceki)})",
        f"Kıyas: {onceki_label} → güncel dönem.",
    ]


def compute_ay_karsilastirma(veri: AnalizVeriSeti) -> AyKarsilastirma | None:
    """Önceki ay verisi varsa 4 temel metrik kıyaslaması üretir."""
    onceki = previous_analiz_ayi(veri.analiz_ayi)
    if not veri_has_ay(veri, onceki):
        return None

    pl_cur = analyze_monthly_pl(
        veri.analiz_ayi,
        veri.muavin_df,
        veri.alis_fatura_df,
        veri.satis_fatura_df,
        maas_harici=veri.maas.toplam_harici_maas,
        personel_maaslari=veri.maas.personel_maaslari,
        dukkan_metrekare=veri.dukkan_metrekare,
    )
    pl_prev = analyze_monthly_pl(
        onceki,
        veri.muavin_df,
        veri.alis_fatura_df,
        veri.satis_fatura_df,
        maas_harici=veri.maas.toplam_harici_maas,
        personel_maaslari=veri.maas.personel_maaslari,
        dukkan_metrekare=veri.dukkan_metrekare,
    )
    nakit_cur = analyze_nakit_akis(veri.banka_df, veri.analiz_ayi)
    nakit_prev = analyze_nakit_akis(veri.banka_df, onceki)

    result = AyKarsilastirma(
        onceki_ayi=onceki,
        net_kar=pl_cur.aylik_net_kar,
        net_kar_onceki=pl_prev.aylik_net_kar,
        net_kar_fark=pl_cur.aylik_net_kar - pl_prev.aylik_net_kar,
        brut_kar=pl_cur.brut_kar,
        brut_kar_onceki=pl_prev.brut_kar,
        brut_kar_fark=pl_cur.brut_kar - pl_prev.brut_kar,
        gider=pl_cur.toplam_operasyonel_gider,
        gider_onceki=pl_prev.toplam_operasyonel_gider,
        gider_fark=pl_cur.toplam_operasyonel_gider - pl_prev.toplam_operasyonel_gider,
        nakit_sonu=nakit_cur.donem_sonu_net_nakit,
        nakit_sonu_onceki=nakit_prev.donem_sonu_net_nakit,
        nakit_sonu_fark=nakit_cur.donem_sonu_net_nakit - nakit_prev.donem_sonu_net_nakit,
    )
    lines = _ozet_satirlari(result)
    result.yorum = lines[0] if lines else ""
    return result


def karsilastirma_ozet_satirlari(k: AyKarsilastirma) -> list[str]:
    """Rapor bölümü için özet satırları."""
    return _ozet_satirlari(k)
