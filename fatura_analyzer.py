"""
Alış ve satış fatura dökümlerini stok kodu bazında eşleştirir;
brüt kar marjı ve markup hesaplar.

MUH ve AD-MUH ile başlayan muhtelif kodlar ana analiz dışı bırakılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from parse_utils import format_tl

KAR_LIST_LIMIT = 10
DUSUK_MARJ_ESIK = 10.0
ESLESMEYEN_SATIS_ESIK = 20.0
SUPHELI_MARJ_ESIK = 150.0
SUPHELI_BF_ORAN = 10.0


def is_analiz_disı_stok_kodu(stok_kodu: str) -> bool:
    """MUH ve AD-MUH ile başlayan muhtelif stok kodlarını tanır."""
    k = str(stok_kodu).strip().upper()
    return k.startswith("MUH") or k.startswith("AD-MUH")


def _is_supheli_eslesme(kalem: StokKarSatir) -> bool:
    """Aşırı marj veya birim fiyat farkı olan eşleşmeleri işaretler."""
    if abs(kalem.kar_marji_pct) > SUPHELI_MARJ_ESIK:
        return True
    alis_bf = kalem.ort_alis_bf
    satis_bf = kalem.ort_satis_bf
    if alis_bf > 0 and satis_bf > 0:
        oran = max(alis_bf, satis_bf) / min(alis_bf, satis_bf)
        if oran > SUPHELI_BF_ORAN:
            return True
    return False


@dataclass
class FaturaStokOzet:
    stok_kodu: str
    stok_adi: str
    miktar: float
    net_tutar: float
    agirlikli_ort_bf: float


@dataclass
class StokKarSatir:
    stok_kodu: str
    stok_adi: str
    ort_alis_bf: float
    ort_satis_bf: float
    satis_miktar: float
    satis_net_tutar: float
    maliyet: float
    kar_tutari: float
    kar_marji_pct: float
    markup_pct: float

    @property
    def label(self) -> str:
        ad = self.stok_adi[:40] + "…" if len(self.stok_adi) > 40 else self.stok_adi
        return f"{self.stok_kodu} — {ad}"


@dataclass
class FaturaKarSonuc:
    dokum_tarihi: str = ""
    eslesen_stok_sayisi: int = 0
    toplam_satis_tutar: float = 0.0
    toplam_alis_tutar: float = 0.0
    eslesen_satis_tutar: float = 0.0
    eslesmeyen_satis_tutar: float = 0.0
    eslesme_orani_pct: float = 0.0
    toplam_brut_kar: float = 0.0
    agirlikli_marj_pct: float = 0.0
    agirlikli_markup_pct: float = 0.0
    sadece_alis_tutar: float = 0.0
    sadece_alis_stok_sayisi: int = 0
    zararli_stok_sayisi: int = 0
    dusuk_marj_stok_sayisi: int = 0
    muhtelif_satis_tutar: float = 0.0
    muhtelif_alis_tutar: float = 0.0
    muhtelif_stok_sayisi: int = 0
    muhtelif_eslesen_sayisi: int = 0
    eslesen_kalemler: list[StokKarSatir] = field(default_factory=list)
    en_yuksek_kar: list[StokKarSatir] = field(default_factory=list)
    en_dusuk_marj: list[StokKarSatir] = field(default_factory=list)
    eslesmeyen_satis: list[FaturaStokOzet] = field(default_factory=list)
    sadece_alis: list[FaturaStokOzet] = field(default_factory=list)
    muhtelif_satis: list[FaturaStokOzet] = field(default_factory=list)
    muhtelif_alis: list[FaturaStokOzet] = field(default_factory=list)
    supheli_eslesme: list[StokKarSatir] = field(default_factory=list)
    yorum: str = ""


def _aggregate_by_stok(df: pd.DataFrame) -> dict[str, FaturaStokOzet]:
    if df is None or df.empty:
        return {}

    grouped = df.groupby("stok_kodu", sort=False)
    result: dict[str, FaturaStokOzet] = {}
    for kod, grp in grouped:
        kod_str = str(kod).strip()
        if not kod_str or kod_str.lower() == "nan":
            continue
        miktar = float(grp["miktar"].sum())
        net_tutar = float(grp["net_tutar"].sum())
        ort_bf = net_tutar / miktar if miktar > 0 else 0.0
        adi = str(grp["stok_adi"].iloc[0]) if "stok_adi" in grp.columns else ""
        result[kod_str] = FaturaStokOzet(
            stok_kodu=kod_str,
            stok_adi=adi,
            miktar=miktar,
            net_tutar=net_tutar,
            agirlikli_ort_bf=ort_bf,
        )
    return result


def _split_agg(
    agg: dict[str, FaturaStokOzet],
) -> tuple[dict[str, FaturaStokOzet], dict[str, FaturaStokOzet]]:
    analiz: dict[str, FaturaStokOzet] = {}
    muhtelif: dict[str, FaturaStokOzet] = {}
    for kod, ozet in agg.items():
        if is_analiz_disı_stok_kodu(kod):
            muhtelif[kod] = ozet
        else:
            analiz[kod] = ozet
    return analiz, muhtelif


def _build_kar_satir(kod: str, alis: FaturaStokOzet, satis: FaturaStokOzet) -> StokKarSatir:
    maliyet = alis.agirlikli_ort_bf * satis.miktar
    kar = satis.net_tutar - maliyet
    marj = (kar / satis.net_tutar * 100) if satis.net_tutar else 0.0
    markup = (kar / maliyet * 100) if maliyet else 0.0
    return StokKarSatir(
        stok_kodu=kod,
        stok_adi=satis.stok_adi or alis.stok_adi,
        ort_alis_bf=alis.agirlikli_ort_bf,
        ort_satis_bf=satis.agirlikli_ort_bf,
        satis_miktar=satis.miktar,
        satis_net_tutar=satis.net_tutar,
        maliyet=maliyet,
        kar_tutari=kar,
        kar_marji_pct=marj,
        markup_pct=markup,
    )


def _build_yorum(sonuc: FaturaKarSonuc) -> str:
    parts: list[str] = []

    if sonuc.muhtelif_stok_sayisi > 0:
        parts.append(
            f"MUH / AD-MUH ile başlayan {sonuc.muhtelif_stok_sayisi} muhtelif stok kodu analiz dışı "
            f"bırakıldı (satış {format_tl(sonuc.muhtelif_satis_tutar)}, "
            f"alış {format_tl(sonuc.muhtelif_alis_tutar)})."
        )

    if sonuc.agirlikli_marj_pct < 0:
        parts.append(
            f"Eşleşen satışlarda ortalama brüt kar marjı negatif (%{sonuc.agirlikli_marj_pct:.1f}); "
            f"zararlı satış kalemleri acil gözden geçirilmeli."
        )
    elif sonuc.agirlikli_marj_pct < DUSUK_MARJ_ESIK:
        parts.append(
            f"Ortalama brüt kar marjı düşük seviyede (%{sonuc.agirlikli_marj_pct:.1f}); "
            f"maliyet ve satış fiyatları birlikte değerlendirilmeli."
        )
    elif sonuc.agirlikli_marj_pct < 25:
        parts.append(
            f"Ortalama brüt kar marjı orta seviyede (%{sonuc.agirlikli_marj_pct:.1f}); "
            f"markup oranı %{sonuc.agirlikli_markup_pct:.1f}."
        )
    else:
        parts.append(
            f"Ortalama brüt kar marjı iyi seviyede (%{sonuc.agirlikli_marj_pct:.1f}); "
            f"markup oranı %{sonuc.agirlikli_markup_pct:.1f}."
        )

    parts.append(
        f"Analiz kapsamında eşleşen {sonuc.eslesen_stok_sayisi} stok kodundan tahmini brüt kar "
        f"{format_tl(sonuc.toplam_brut_kar)}; eşleşen satış payı %{sonuc.eslesme_orani_pct:.1f}."
    )

    if sonuc.eslesmeyen_satis_tutar > 0:
        eslesmeyen_oran = (
            sonuc.eslesmeyen_satis_tutar / sonuc.toplam_satis_tutar * 100
            if sonuc.toplam_satis_tutar
            else 0.0
        )
        parts.append(
            f"Eşleşmeyen satış (bilgi): {format_tl(sonuc.eslesmeyen_satis_tutar)} "
            f"(analiz kapsamı satışının %{eslesmeyen_oran:.1f}'i); "
            f"stok kodu veya alış kaydı eksikliği kontrol edilmeli."
        )

    if sonuc.supheli_eslesme:
        parts.append(
            f"{len(sonuc.supheli_eslesme)} stok kodu şüpheli eşleşme olarak ayrıldı "
            f"(aşırı marj veya birim fiyat farkı); kar KPI'larına dahil edilmedi."
        )

    if sonuc.zararli_stok_sayisi > 0:
        parts.append(
            f"{sonuc.zararli_stok_sayisi} stok kodunda satış, ağırlıklı alış maliyetinin altında."
        )

    if sonuc.sadece_alis_stok_sayisi > 0:
        parts.append(
            f"{sonuc.sadece_alis_stok_sayisi} stok kodu yalnızca alışta görünüyor "
            f"(toplam {format_tl(sonuc.sadece_alis_tutar)}); stok birikimi olasılığı var."
        )

    return " ".join(parts)


def analyze_fatura_kar(
    alis_df: pd.DataFrame | None,
    satis_df: pd.DataFrame | None,
) -> FaturaKarSonuc | None:
    """Alış ve satış fatura dökümlerini eşleştirip kar analizi üretir."""
    if alis_df is None or satis_df is None or alis_df.empty or satis_df.empty:
        return None

    alis_agg_all = _aggregate_by_stok(alis_df)
    satis_agg_all = _aggregate_by_stok(satis_df)

    if not alis_agg_all or not satis_agg_all:
        return None

    alis_agg, alis_muh = _split_agg(alis_agg_all)
    satis_agg, satis_muh = _split_agg(satis_agg_all)

    dokum_tarihi = ""
    if "dokum_tarihi" in alis_df.columns and alis_df["dokum_tarihi"].iloc[0]:
        dokum_tarihi = str(alis_df["dokum_tarihi"].iloc[0])
    elif "dokum_tarihi" in satis_df.columns and satis_df["dokum_tarihi"].iloc[0]:
        dokum_tarihi = str(satis_df["dokum_tarihi"].iloc[0])

    toplam_satis = sum(s.net_tutar for s in satis_agg.values())
    toplam_alis = sum(a.net_tutar for a in alis_agg.values())

    muhtelif_satis_tutar = sum(s.net_tutar for s in satis_muh.values())
    muhtelif_alis_tutar = sum(a.net_tutar for a in alis_muh.values())
    muhtelif_kodlar = set(alis_muh.keys()) | set(satis_muh.keys())
    muhtelif_eslesen = set(alis_muh.keys()) & set(satis_muh.keys())

    eslesen_kalemler: list[StokKarSatir] = []
    supheli_eslesme: list[StokKarSatir] = []
    common = set(alis_agg.keys()) & set(satis_agg.keys())

    for kod in sorted(common):
        kalem = _build_kar_satir(kod, alis_agg[kod], satis_agg[kod])
        if _is_supheli_eslesme(kalem):
            supheli_eslesme.append(kalem)
        else:
            eslesen_kalemler.append(kalem)

    eslesen_satis = sum(k.satis_net_tutar for k in eslesen_kalemler)
    toplam_kar = sum(k.kar_tutari for k in eslesen_kalemler)
    toplam_maliyet = sum(k.maliyet for k in eslesen_kalemler)
    agirlikli_marj = (toplam_kar / eslesen_satis * 100) if eslesen_satis else 0.0
    agirlikli_markup = (toplam_kar / toplam_maliyet * 100) if toplam_maliyet else 0.0

    only_satis = set(satis_agg.keys()) - set(alis_agg.keys())
    only_alis = set(alis_agg.keys()) - set(satis_agg.keys())

    eslesmeyen_satis_list = sorted(
        [satis_agg[k] for k in only_satis],
        key=lambda x: x.net_tutar,
        reverse=True,
    )
    sadece_alis_list = sorted(
        [alis_agg[k] for k in only_alis],
        key=lambda x: x.net_tutar,
        reverse=True,
    )

    muhtelif_satis_list = sorted(
        satis_muh.values(),
        key=lambda x: x.net_tutar,
        reverse=True,
    )
    muhtelif_alis_list = sorted(
        alis_muh.values(),
        key=lambda x: x.net_tutar,
        reverse=True,
    )

    eslesmeyen_tutar = sum(s.net_tutar for s in eslesmeyen_satis_list)
    sadece_alis_tutar = sum(a.net_tutar for a in sadece_alis_list)

    en_yuksek_kar = sorted(eslesen_kalemler, key=lambda k: k.kar_tutari, reverse=True)[
        :KAR_LIST_LIMIT
    ]
    en_dusuk_marj = sorted(eslesen_kalemler, key=lambda k: k.kar_marji_pct)[:KAR_LIST_LIMIT]

    sonuc = FaturaKarSonuc(
        dokum_tarihi=dokum_tarihi,
        eslesen_stok_sayisi=len(eslesen_kalemler),
        toplam_satis_tutar=toplam_satis,
        toplam_alis_tutar=toplam_alis,
        eslesen_satis_tutar=eslesen_satis,
        eslesmeyen_satis_tutar=eslesmeyen_tutar,
        eslesme_orani_pct=(eslesen_satis / toplam_satis * 100) if toplam_satis else 0.0,
        toplam_brut_kar=toplam_kar,
        agirlikli_marj_pct=agirlikli_marj,
        agirlikli_markup_pct=agirlikli_markup,
        sadece_alis_tutar=sadece_alis_tutar,
        sadece_alis_stok_sayisi=len(sadece_alis_list),
        zararli_stok_sayisi=sum(1 for k in eslesen_kalemler if k.kar_marji_pct < 0),
        dusuk_marj_stok_sayisi=sum(1 for k in eslesen_kalemler if k.kar_marji_pct < DUSUK_MARJ_ESIK),
        muhtelif_satis_tutar=muhtelif_satis_tutar,
        muhtelif_alis_tutar=muhtelif_alis_tutar,
        muhtelif_stok_sayisi=len(muhtelif_kodlar),
        muhtelif_eslesen_sayisi=len(muhtelif_eslesen),
        eslesen_kalemler=eslesen_kalemler,
        en_yuksek_kar=en_yuksek_kar,
        en_dusuk_marj=en_dusuk_marj,
        eslesmeyen_satis=eslesmeyen_satis_list,
        sadece_alis=sadece_alis_list,
        muhtelif_satis=muhtelif_satis_list,
        muhtelif_alis=muhtelif_alis_list,
        supheli_eslesme=supheli_eslesme,
    )
    sonuc.yorum = _build_yorum(sonuc)
    return sonuc
