"""
120/320 plan ile fatura-banka yaşlandırma mutabakatı.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cari_plan_analyzer import CariPlanSonuc
from parse_utils import format_tl
from reconciliation_analyzer import YaslandirmaSonuc

MUTABAKAT_TUTAR_ESIK = 50_000.0
MUTABAKAT_ORAN_ESIK = 0.20


@dataclass
class PlanMutabakatSonuc:
    tahsilat_plan_acik: float = 0.0
    tahsil_edilemeyen: float = 0.0
    tahsilat_fark: float = 0.0
    odeme_plan_acik: float = 0.0
    odenmeyen: float = 0.0
    odeme_fark: float = 0.0
    yorumlar: list[str] = field(default_factory=list)


def _anlamli_fark(plan: float, yas: float) -> bool:
    fark = abs(plan - yas)
    if fark >= MUTABAKAT_TUTAR_ESIK:
        return True
    base = max(abs(plan), abs(yas), 1.0)
    return fark / base >= MUTABAKAT_ORAN_ESIK


def build_plan_mutabakat(
    tahsilat_plan: CariPlanSonuc | None,
    tediye_plan: CariPlanSonuc | None,
    yaslandirma: YaslandirmaSonuc,
) -> PlanMutabakatSonuc | None:
    """Plan snapshot ile yaşlandırma toplamlarını karşılaştırır."""
    has_tahsil = tahsilat_plan is not None and tahsilat_plan.hesap_sayisi > 0
    has_tediye = tediye_plan is not None and tediye_plan.hesap_sayisi > 0
    if not has_tahsil and not has_tediye:
        return None

    tahsil_plan_acik = tahsilat_plan.toplam_acik if has_tahsil else 0.0
    tahsil_yas = yaslandirma.toplam_tahsil_edilemeyen
    odeme_plan_acik = tediye_plan.toplam_acik if has_tediye else 0.0
    odeme_yas = yaslandirma.toplam_odenmeyen

    yorumlar = [
        "Plan: ERP anlık bakiye (120/320). Yaşlandırma: fatura − banka farkı (dönemsel).",
    ]

    tahsil_fark = tahsil_plan_acik - tahsil_yas
    odeme_fark = odeme_plan_acik - odeme_yas

    if has_tahsil:
        if _anlamli_fark(tahsil_plan_acik, tahsil_yas):
            yorumlar.append(
                f"Tahsilat farkı {format_tl(abs(tahsil_fark))} "
                f"(plan {format_tl(tahsil_plan_acik)} vs yaşlandırma {format_tl(tahsil_yas)})."
            )
        else:
            yorumlar.append(
                f"Tahsilat planı ile yaşlandırma uyumlu "
                f"(plan {format_tl(tahsil_plan_acik)}, yaşlandırma {format_tl(tahsil_yas)})."
            )

    if has_tediye:
        if _anlamli_fark(odeme_plan_acik, odeme_yas):
            yorumlar.append(
                f"Ödeme farkı {format_tl(abs(odeme_fark))} "
                f"(plan {format_tl(odeme_plan_acik)} vs yaşlandırma {format_tl(odeme_yas)})."
            )
        else:
            yorumlar.append(
                f"Ödeme planı ile yaşlandırma uyumlu "
                f"(plan {format_tl(odeme_plan_acik)}, yaşlandırma {format_tl(odeme_yas)})."
            )

    return PlanMutabakatSonuc(
        tahsilat_plan_acik=tahsil_plan_acik,
        tahsil_edilemeyen=tahsil_yas,
        tahsilat_fark=tahsil_fark,
        odeme_plan_acik=odeme_plan_acik,
        odenmeyen=odeme_yas,
        odeme_fark=odeme_fark,
        yorumlar=yorumlar,
    )
