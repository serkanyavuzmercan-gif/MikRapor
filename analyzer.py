"""
Ay bazlı finansal analiz rapor motoru.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from cari_plan_analyzer import (
    CariPlanSonuc,
    analyze_cari_plan,
    compute_vade_net,
    plan_ozet_metin,
)
from cashflow_analyzer import NakitAkisOzeti, analyze_nakit_akis
from cfo_analyzer import CfoErkenUyariSonuc, analyze_cfo_uyarilari
from fatura_analyzer import is_analiz_disı_stok_kodu
from models import AnalizVeriSeti
from monthly_pl_analyzer import MonthlyPLSonuc, analyze_monthly_pl
from operational_analyzer import KAR_TANIMLARI
from parse_utils import format_tl
from period_utils import analiz_ayi_label, filter_df_by_analiz_ayi, format_analiz_donem
from plan_mutabakat import PlanMutabakatSonuc, build_plan_mutabakat
from reconciliation_analyzer import (
    VeriEslesmeSonuc,
    YaslandirmaSonuc,
    analyze_reconciliation,
    banka_120_giris_toplam,
)
from trend_analyzer import AyKarsilastirma, compute_ay_karsilastirma, karsilastirma_ozet_satirlari


@dataclass
class ReportContext:
    analiz_ayi: str = ""
    donem_metin: str = ""
    muavin_ref: str = ""
    alis_fatura_ref: str = ""
    satis_fatura_ref: str = ""
    banka_ref: str = ""
    tahsilat_plan_ref: str = ""
    tediye_plan_ref: str = ""
    uyari_mesajlari: list[str] = field(default_factory=list)


@dataclass
class SummarySection:
    baslik: str
    satirlar: list[str] = field(default_factory=list)


@dataclass
class MonthlyAnalysisReport:
    analiz_ayi: str
    context: ReportContext
    cfo_uyarilari: CfoErkenUyariSonuc
    nakit_akis: NakitAkisOzeti
    aylik_pl: MonthlyPLSonuc
    yaslandirma: YaslandirmaSonuc
    eslesme: VeriEslesmeSonuc
    fatura_kar: object | None = None
    kar_tanimlari: list[str] = field(default_factory=lambda: list(KAR_TANIMLARI))
    recommendations: list = field(default_factory=list)
    executive_wrap_up: list[str] = field(default_factory=list)
    summary_sections: list[SummarySection] = field(default_factory=list)
    summary_text: str = ""
    tahsilat_plan: CariPlanSonuc | None = None
    tediye_plan: CariPlanSonuc | None = None
    vade_net: float | None = None
    guvenilirlik_endeks: str = ""
    guvenilirlik_aciklama: str = ""
    ay_karsilastirma: AyKarsilastirma | None = None
    plan_mutabakat: PlanMutabakatSonuc | None = None

    @property
    def donem(self) -> str:
        return self.context.donem_metin


def _fatura_toplam(df: pd.DataFrame | None) -> float:
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for _, row in df.iterrows():
        if is_analiz_disı_stok_kodu(str(row.get("stok_kodu", ""))):
            continue
        total += float(row.get("net_tutar", 0) or 0)
    return total


def build_report_context(veri: AnalizVeriSeti, uyari: list[str] | None = None) -> ReportContext:
    banka_names = ", ".join(veri.banka_paths) if veri.banka_paths else ""
    return ReportContext(
        analiz_ayi=veri.analiz_ayi,
        donem_metin=format_analiz_donem(veri.analiz_ayi),
        muavin_ref=veri.muavin_path or ("Yüklü" if veri.has_muavin else "—"),
        alis_fatura_ref=veri.alis_fatura_path or ("Yüklü" if not veri.alis_fatura_df.empty else "—"),
        satis_fatura_ref=veri.satis_fatura_path or ("Yüklü" if not veri.satis_fatura_df.empty else "—"),
        banka_ref=banka_names or ("Yüklü" if veri.has_banka else "—"),
        tahsilat_plan_ref=veri.tahsilat_plan_path or ("Yüklü" if veri.has_tahsilat_plan else "—"),
        tediye_plan_ref=veri.tediye_plan_path or ("Yüklü" if veri.has_tediye_plan else "—"),
        uyari_mesajlari=uyari or [],
    )


def build_executive_summary(report: MonthlyAnalysisReport) -> tuple[str, list[SummarySection]]:
    pl = report.aylik_pl
    nakit = report.nakit_akis
    cfo = report.cfo_uyarilari
    sections: list[SummarySection] = [
        SummarySection(
            baslik="CFO Erken Uyarı",
            satirlar=[g.aciklama for g in cfo.gostergeler],
        ),
        SummarySection(
            baslik="Aylık Kâr/Zarar",
            satirlar=[
                f"Brüt kâr: {format_tl(pl.brut_kar)}",
                f"Operasyonel gider: {format_tl(pl.toplam_operasyonel_gider)}",
                f"Harici maaş: {format_tl(pl.toplam_harici_maas)}",
                f"Net: {format_tl(pl.aylik_net_kar)}",
            ],
        ),
        SummarySection(
            baslik="Nakit Akış",
            satirlar=[nakit.yorum] if nakit.yorum else ["Banka verisi yok."],
        ),
        SummarySection(
            baslik="Yaşlandırma",
            satirlar=[
                f"Tahsil edilemeyen: {format_tl(report.yaslandirma.toplam_tahsil_edilemeyen)}",
                f"Ödenmeyen: {format_tl(report.yaslandirma.toplam_odenmeyen)}",
            ],
        ),
    ]
    if report.tahsilat_plan or report.tediye_plan:
        plan_lines = plan_ozet_metin(report.tahsilat_plan, report.tediye_plan)
        if plan_lines:
            sections.append(SummarySection(baslik="Tahsilat ve Ödeme Planı", satirlar=plan_lines))
    if report.ay_karsilastirma:
        sections.append(
            SummarySection(
                baslik="Önceki Aya Göre",
                satirlar=karsilastirma_ozet_satirlari(report.ay_karsilastirma),
            )
        )
    if report.plan_mutabakat:
        sections.append(
            SummarySection(
                baslik="Plan Mutabakatı",
                satirlar=list(report.plan_mutabakat.yorumlar),
            )
        )
    text = (
        f"{analiz_ayi_label(report.analiz_ayi)} finansal özeti. "
        f"Net kâr/zarar {format_tl(pl.aylik_net_kar)}; "
        f"dönem sonu nakit {format_tl(nakit.donem_sonu_net_nakit)}. "
        f"{cfo.ozet_metin}"
    )
    return text, sections


def run_monthly_analysis(veri: AnalizVeriSeti) -> MonthlyAnalysisReport:
    """4 veri kaynağından aylık finansal analiz raporu üretir."""
    uyari: list[str] = []
    if not veri.has_muavin:
        uyari.append("Muavin defteri yüklenmedi; operasyonel giderler hesaplanamaz.")
    if not veri.has_fatura:
        uyari.append("Fatura verisi yüklenmedi; brüt kâr hesaplanamaz.")
    else:
        has_alis = not veri.alis_fatura_df.empty
        has_satis = not veri.satis_fatura_df.empty
        if has_alis != has_satis:
            uyari.append("Brüt kâr için hem alış hem satış faturası gerekli.")
    if not veri.has_banka:
        uyari.append("Banka hareketleri yüklenmedi; nakit akışı ve eşleştirme sınırlı.")
    if not veri.has_tahsilat_plan:
        uyari.append("120 tahsilat planı yüklenmedi.")
    if not veri.has_tediye_plan:
        uyari.append("320 ödeme planı yüklenmedi.")
    if (veri.has_tahsilat_plan or veri.has_tediye_plan) and not (
        veri.has_tahsilat_plan and veri.has_tediye_plan
    ):
        uyari.append("Vade neti için hem 120 tahsilat hem 320 ödeme planı gerekli.")

    tahsilat_plan = analyze_cari_plan(veri.tahsilat_plan_df) if veri.has_tahsilat_plan else None
    tediye_plan = analyze_cari_plan(veri.tediye_plan_df) if veri.has_tediye_plan else None
    vade_net = compute_vade_net(tahsilat_plan, tediye_plan)

    aylik_pl = analyze_monthly_pl(
        veri.analiz_ayi,
        veri.muavin_df,
        veri.alis_fatura_df,
        veri.satis_fatura_df,
        maas_harici=veri.maas.toplam_harici_maas,
        personel_maaslari=veri.maas.personel_maaslari,
        dukkan_metrekare=veri.dukkan_metrekare,
    )

    nakit = analyze_nakit_akis(veri.banka_df, veri.analiz_ayi)
    yaslandirma, eslesme = analyze_reconciliation(
        veri.muavin_df,
        veri.alis_fatura_df,
        veri.satis_fatura_df,
        veri.banka_df,
        veri.analiz_ayi,
    )

    satis_ay = filter_df_by_analiz_ayi(veri.satis_fatura_df, "tarih", veri.analiz_ayi)
    ay_satis = _fatura_toplam(satis_ay)
    banka_120 = banka_120_giris_toplam(veri.banka_df, veri.analiz_ayi)

    cfo = analyze_cfo_uyarilari(
        aylik_pl,
        nakit,
        yaslandirma,
        eslesme,
        ay_satis_fatura_toplam=ay_satis,
        ay_banka_120_giris=banka_120,
        vade_net=vade_net,
        vade_net_eksik=(veri.has_tahsilat_plan or veri.has_tediye_plan)
        and not (veri.has_tahsilat_plan and veri.has_tediye_plan),
    )

    context = build_report_context(veri, uyari)
    ay_karsilastirma = compute_ay_karsilastirma(veri)
    plan_mutabakat = build_plan_mutabakat(tahsilat_plan, tediye_plan, yaslandirma)

    report = MonthlyAnalysisReport(
        analiz_ayi=veri.analiz_ayi,
        context=context,
        cfo_uyarilari=cfo,
        nakit_akis=nakit,
        aylik_pl=aylik_pl,
        yaslandirma=yaslandirma,
        eslesme=eslesme,
        fatura_kar=aylik_pl.fatura_kar,
        tahsilat_plan=tahsilat_plan,
        tediye_plan=tediye_plan,
        vade_net=vade_net,
        ay_karsilastirma=ay_karsilastirma,
        plan_mutabakat=plan_mutabakat,
    )
    return _finalize_report(report)


def _finalize_report(report: MonthlyAnalysisReport) -> MonthlyAnalysisReport:
    from advisor import build_executive_wrap_up, build_recommendations
    from risk_analyzer import analyze_guvenilirlik

    guv = analyze_guvenilirlik(report)
    report.guvenilirlik_endeks = guv.endeks
    report.guvenilirlik_aciklama = (
        f"Veri güvenilirliği: {guv.endeks}"
        + (f" — {'; '.join(guv.uyari_mesajlari)}" if guv.uyari_mesajlari else "")
    )

    report.recommendations = build_recommendations(report)
    report.executive_wrap_up = build_executive_wrap_up(report)
    report.summary_text, report.summary_sections = build_executive_summary(report)
    return report
