"""
CFO erken uyarı göstergeleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cashflow_analyzer import NakitAkisOzeti
from metric_labels import metric_kaynak, metric_short
from monthly_pl_analyzer import MonthlyPLSonuc
from parse_utils import format_tl
from reconciliation_analyzer import VeriEslesmeSonuc, YaslandirmaSonuc


@dataclass
class CfoGosterge:
    ad: str
    deger: str
    durum: str = "normal"
    aciklama: str = ""


@dataclass
class CfoErkenUyariSonuc:
    aylik_net_kar: float = 0.0
    nakit_donusum_hizi_pct: float = 0.0
    sirket_omru_ay: float | None = None
    runway_modu: str = ""
    veri_eslesme_skoru_pct: float = 0.0
    gostergeler: list[CfoGosterge] = field(default_factory=list)
    ozet_metin: str = ""


def _durum_for_net_kar(net: float) -> str:
    if net < 0:
        return "kritik"
    if net < 10000:
        return "uyari"
    return "iyi"


def _durum_for_runway(ay: float | None) -> str:
    if ay is None:
        return "bilinmiyor"
    if ay < 1:
        return "kritik"
    if ay < 3:
        return "uyari"
    return "iyi"


def _durum_for_vade_net(net: float | None) -> str:
    if net is None:
        return "bilinmiyor"
    if net < 0:
        return "kritik"
    if net < 50000:
        return "uyari"
    return "iyi"


def _durum_for_tahsil_acigi(tutar: float) -> str:
    if tutar <= 0:
        return "iyi"
    if tutar > 500_000:
        return "kritik"
    if tutar > 100_000:
        return "uyari"
    return "normal"


def analyze_cfo_uyarilari(
    aylik_pl: MonthlyPLSonuc,
    nakit: NakitAkisOzeti,
    yaslandirma: YaslandirmaSonuc,
    eslesme: VeriEslesmeSonuc,
    ay_satis_fatura_toplam: float = 0.0,
    ay_banka_120_giris: float = 0.0,
    vade_net: float | None = None,
    *,
    vade_net_eksik: bool = False,
) -> CfoErkenUyariSonuc:
    """CFO erken uyarı KPI'larını hesaplar."""
    net = aylik_pl.aylik_net_kar
    aylik_gider = aylik_pl.toplam_operasyonel_gider + aylik_pl.toplam_harici_maas

    nakit_donusum = 0.0
    if ay_satis_fatura_toplam > 0:
        nakit_donusum = min(ay_banka_120_giris / ay_satis_fatura_toplam * 100, 100.0)

    runway = None
    runway_modu = ""
    nakit_sonu = nakit.donem_sonu_net_nakit
    if nakit_sonu > 0:
        if net < 0:
            burn = abs(net)
            if burn > 0:
                runway = nakit_sonu / burn
                runway_modu = "zarar"
        elif aylik_gider > 0:
            runway = nakit_sonu / aylik_gider
            runway_modu = "gider"

    skor = eslesme.eslesme_skoru_pct

    runway_aciklama = metric_kaynak("runway")
    if runway_modu == "zarar":
        runway_aciklama = "Zarar modu: dönem sonu nakit / aylık net zarar"
    elif runway_modu == "gider":
        runway_aciklama = "Kâr modu: dönem sonu nakit / aylık gider"

    gostergeler = [
        CfoGosterge(
            ad=metric_short("aylik_net_kar"),
            deger=format_tl(net),
            durum=_durum_for_net_kar(net),
            aciklama=metric_kaynak("aylik_net_kar"),
        ),
        CfoGosterge(
            ad=metric_short("nakit_donusum"),
            deger=f"%{nakit_donusum:.1f}",
            durum="uyari" if nakit_donusum < 50 else "iyi",
            aciklama=metric_kaynak("nakit_donusum"),
        ),
        CfoGosterge(
            ad=metric_short("runway"),
            deger=f"{runway:.1f} ay" if runway is not None else "—",
            durum=_durum_for_runway(runway),
            aciklama=runway_aciklama,
        ),
        CfoGosterge(
            ad=metric_short("veri_eslesme"),
            deger=f"%{skor:.1f}",
            durum="uyari" if skor < 70 else "iyi",
            aciklama=eslesme.yorum or metric_kaynak("veri_eslesme"),
        ),
    ]

    tahsil_acigi = yaslandirma.toplam_tahsil_edilemeyen
    if tahsil_acigi > 0:
        gostergeler.append(
            CfoGosterge(
                ad=metric_short("tahsil_edilemeyen"),
                deger=format_tl(tahsil_acigi),
                durum=_durum_for_tahsil_acigi(tahsil_acigi),
                aciklama=metric_kaynak("tahsil_edilemeyen"),
            )
        )

    if vade_net is not None:
        gostergeler.append(
            CfoGosterge(
                ad=metric_short("vade_net"),
                deger=format_tl(vade_net),
                durum=_durum_for_vade_net(vade_net),
                aciklama=metric_kaynak("vade_net"),
            )
        )
    elif vade_net_eksik:
        gostergeler.append(
            CfoGosterge(
                ad=metric_short("vade_net"),
                deger="—",
                durum="bilinmiyor",
                aciklama="Vade neti için hem 120 tahsilat hem 320 ödeme planı gerekli.",
            )
        )

    ozet = " | ".join(f"{g.ad}: {g.deger}" for g in gostergeler[:4])
    if len(gostergeler) > 4:
        ozet += " | " + " | ".join(f"{g.ad}: {g.deger}" for g in gostergeler[4:])

    return CfoErkenUyariSonuc(
        aylik_net_kar=net,
        nakit_donusum_hizi_pct=nakit_donusum,
        sirket_omru_ay=runway,
        runway_modu=runway_modu,
        veri_eslesme_skoru_pct=skor,
        gostergeler=gostergeler,
        ozet_metin=ozet,
    )
