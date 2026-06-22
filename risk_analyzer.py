"""
Güvenilirlik ve veri kalitesi risk analizi (ay bazlı mimari).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from analyzer import MonthlyAnalysisReport, format_tl

ESLESMEYEN_GUVENILIRLIK_ESIK = 20.0
MUH_SATIS_ORAN_ESIK = 5.0


@dataclass
class GuvenilirlikSonuc:
    endeks: str = "YUKSEK"
    eslesmeyen_oran: float = 0.0
    muh_oran: float = 0.0
    uyari_mesajlari: list[str] = field(default_factory=list)


def analyze_guvenilirlik(report: MonthlyAnalysisReport) -> GuvenilirlikSonuc:
    """Fatura eşleşme güvenilirliğini hesaplar."""
    uyari: list[str] = []
    fk = report.fatura_kar
    eslesmeyen_oran = 0.0
    muh_oran = 0.0

    if fk and fk.toplam_satis_tutar > 0:
        eslesmeyen_oran = fk.eslesmeyen_satis_tutar / fk.toplam_satis_tutar * 100.0
        muh_oran = fk.muhtelif_satis_tutar / fk.toplam_satis_tutar * 100.0
    elif fk:
        eslesmeyen_oran = 100.0 - fk.eslesme_orani_pct

    endeks = "YUKSEK"
    if eslesmeyen_oran > ESLESMEYEN_GUVENILIRLIK_ESIK:
        endeks = "DUSUK"
        uyari.append(f"Eşleşmeyen satış %{eslesmeyen_oran:.1f}.")
    elif muh_oran > MUH_SATIS_ORAN_ESIK:
        endeks = "ORTA"
        uyari.append(f"MUH/AD-MUH payı %{muh_oran:.1f}.")

    return GuvenilirlikSonuc(
        endeks=endeks,
        eslesmeyen_oran=eslesmeyen_oran,
        muh_oran=muh_oran,
        uyari_mesajlari=uyari,
    )


def build_risk_recommendations(report: MonthlyAnalysisReport) -> list:
    from advisor import Recommendation

    recs: list[Recommendation] = []
    guv = analyze_guvenilirlik(report)
    fk = report.fatura_kar

    if guv.eslesmeyen_oran > ESLESMEYEN_GUVENILIRLIK_ESIK and fk:
        recs.append(
            Recommendation(
                kategori="Veri",
                oncelik="yüksek",
                baslik="Karlılık güvenilirliği düşük",
                aciklama=(
                    f"Satışın %{guv.eslesmeyen_oran:.1f}'i "
                    f"({format_tl(fk.eslesmeyen_satis_tutar)}) alışla eşleşmiyor."
                ),
            )
        )

    if guv.muh_oran > MUH_SATIS_ORAN_ESIK and fk:
        recs.append(
            Recommendation(
                kategori="Muhasebe",
                oncelik="yüksek",
                baslik="Standart dışı stok kartı",
                aciklama=(
                    f"MUH/AD-MUH satış payı %{guv.muh_oran:.1f} "
                    f"({format_tl(fk.muhtelif_satis_tutar)})."
                ),
            )
        )

    return recs
