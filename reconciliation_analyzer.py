"""
Banka, fatura ve muavin arası eşleştirme ve yaşlandırma (smart v2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from fatura_analyzer import is_analiz_disı_stok_kodu
from monthly_pl_analyzer import OPEX_ANA_HESAPLAR
from parse_utils import extract_ana_hesap, format_tl, karsi_prefix, normalize_hesap_kodu
from period_utils import analiz_ayi_araligi, filter_df_by_analiz_ayi

TOLERANS_ORAN = 0.01
CARI_FALLBACK_PATTERN = re.compile(r"\b(1[02]0\.\d{3,}|3[02]0\.\d{3,}|780\.\d{2,})\b")


@dataclass
class YaslandirmaSatir:
    cari_kodu: str
    cari_adi: str
    fatura_tutari: float
    eslesen_banka: float
    kalan: float
    vade_gun: int = 0
    bucket: str = ""


@dataclass
class AciklanamayanGider:
    tarih: str
    aciklama: str
    tutar: float
    banka_adi: str = ""
    cari_kodu: str = ""
    kategori: str = ""


@dataclass
class YaslandirmaSonuc:
    tahsil_edilemeyen: list[YaslandirmaSatir] = field(default_factory=list)
    odenmeyen: list[YaslandirmaSatir] = field(default_factory=list)
    toplam_tahsil_edilemeyen: float = 0.0
    toplam_odenmeyen: float = 0.0


@dataclass
class VeriEslesmeSonuc:
    eslesme_skoru_pct: float = 0.0
    toplam_banka_cikis: float = 0.0
    eslesen_banka_cikis: float = 0.0
    ic_transfer_cikis: float = 0.0
    vergi_odeme_cikis: float = 0.0
    aciklanamayan_giderler: list[AciklanamayanGider] = field(default_factory=list)
    yorum: str = ""


def _bucket_for_days(days: int) -> str:
    if days <= 30:
        return "0-30 gün"
    if days <= 60:
        return "31-60 gün"
    return "60+ gün"


def _resolve_cari_kodu(row: pd.Series) -> str:
    kod = str(row.get("cari_kodu", "")).strip()
    if kod and kod not in ("nan", "None"):
        return normalize_hesap_kodu(kod)
    aciklama = str(row.get("aciklama", ""))
    match = CARI_FALLBACK_PATTERN.search(aciklama)
    return normalize_hesap_kodu(match.group(1)) if match else ""


def _filter_banka_through_analiz_ayi(banka_df: pd.DataFrame, analiz_ayi: str) -> pd.DataFrame:
    """Analiz ayı sonuna kadar (dahil) tüm banka hareketleri."""
    if banka_df is None or banka_df.empty:
        return pd.DataFrame()
    _bas, bit = analiz_ayi_araligi(analiz_ayi)
    work = banka_df.copy()
    if "tarih" not in work.columns:
        return work
    work["tarih"] = pd.to_datetime(work["tarih"], errors="coerce", dayfirst=True)
    return work[work["tarih"].dt.date <= bit].copy()


def _is_ic_transfer_row(row: pd.Series) -> bool:
    if "ic_transfer" in row.index:
        val = row.get("ic_transfer")
        if pd.notna(val):
            return bool(val)
    prefix = str(row.get("karsi_hesap_prefix", "")) or karsi_prefix(_resolve_cari_kodu(row))
    return prefix == "102"


def _fatura_cari_toplam(
    df: pd.DataFrame,
    cari_prefix: str,
    analiz_ayi: str,
    *,
    include_prior_open: bool = True,
) -> dict[str, dict]:
    if df is None or df.empty:
        return {}

    work = df.copy()
    work["tarih"] = pd.to_datetime(work["tarih"], errors="coerce", dayfirst=True)
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    ref = bit

    result: dict[str, dict] = {}
    for _, row in work.iterrows():
        kod = normalize_hesap_kodu(str(row.get("cari_kodu", "")).strip())
        if not kod.startswith(cari_prefix):
            continue
        if is_analiz_disı_stok_kodu(str(row.get("stok_kodu", ""))):
            continue
        tarih = row["tarih"]
        if pd.isna(tarih):
            continue
        if tarih.date() > bit:
            continue
        if not include_prior_open and tarih.date() < bas:
            continue
        tutar = float(row.get("net_tutar", 0) or 0)
        vade = row.get("vade", pd.NaT)
        vade_gun = 0
        if pd.notna(vade):
            vade_gun = (ref - vade.date()).days if hasattr(vade, "date") else 0
        entry = result.setdefault(
            kod,
            {"cari_adi": str(row.get("cari_adi", "")), "tutar": 0.0, "vade_gun": vade_gun},
        )
        entry["tutar"] += tutar
        if vade_gun > entry["vade_gun"]:
            entry["vade_gun"] = vade_gun
    return result


def _banka_cari_toplam(
    banka_df: pd.DataFrame,
    analiz_ayi: str,
    giris: bool,
    *,
    prefix_filter: str | None = None,
    exclude_ic_transfer: bool = False,
) -> dict[str, float]:
    if banka_df is None or banka_df.empty:
        return {}
    ay = filter_df_by_analiz_ayi(banka_df, "tarih", analiz_ayi)
    col = "giris" if giris else "cikis"
    result: dict[str, float] = {}
    for _, row in ay.iterrows():
        if exclude_ic_transfer and _is_ic_transfer_row(row):
            continue
        kod = _resolve_cari_kodu(row)
        prefix = karsi_prefix(kod)
        if prefix_filter and not prefix.startswith(prefix_filter):
            continue
        if giris and prefix != "120":
            continue
        if not giris and prefix not in ("320",):
            continue
        tutar = float(row.get(col, 0) or 0)
        if tutar <= 0:
            continue
        result[kod] = result.get(kod, 0.0) + tutar
    return result


def banka_120_giris_toplam(banka_df: pd.DataFrame, analiz_ayi: str) -> float:
    """Seçilen ay içi 120 tahsilat banka girişleri (102 transfer hariç)."""
    totals = _banka_cari_toplam(banka_df, analiz_ayi, giris=True, exclude_ic_transfer=True)
    return sum(totals.values())


def _banka_tahsilat_toplam_smart(
    banka_df: pd.DataFrame,
    analiz_ayi: str,
    satis_map: dict[str, dict],
) -> dict[str, float]:
    """120 doğrudan tahsilatlar + toleranslı eşleştirme (dönem sonuna kadar kümülatif)."""
    if banka_df is None or banka_df.empty:
        return {}
    work = _filter_banka_through_analiz_ayi(banka_df, analiz_ayi)
    if work.empty:
        return {}

    result: dict[str, float] = {}
    used_invoice_amounts: dict[str, float] = {}

    for _, row in work.iterrows():
        if _is_ic_transfer_row(row):
            continue
        tutar = float(row.get("giris", 0) or 0)
        if tutar <= 0:
            continue
        kod = _resolve_cari_kodu(row)
        prefix = karsi_prefix(kod)

        if prefix == "120" and kod:
            result[kod] = result.get(kod, 0.0) + tutar
            continue

        best_kod = ""
        best_diff = float("inf")
        for fkod, info in satis_map.items():
            if not fkod.startswith("120"):
                continue
            already = used_invoice_amounts.get(fkod, 0.0)
            kalan = max(info["tutar"] - already, 0.0)
            if kalan <= 0:
                continue
            diff = abs(kalan - tutar)
            tol = max(kalan, tutar) * TOLERANS_ORAN
            if diff <= max(tol, 1.0) and diff < best_diff:
                best_diff = diff
                best_kod = fkod
        if best_kod:
            result[best_kod] = result.get(best_kod, 0.0) + tutar
            used_invoice_amounts[best_kod] = used_invoice_amounts.get(best_kod, 0.0) + tutar

    return result


def _banka_odeme_toplam_smart(
    banka_df: pd.DataFrame,
    analiz_ayi: str,
    alis_map: dict[str, dict],
) -> dict[str, float]:
    """320 doğrudan ödemeler + toleranslı cari eşleştirme (dönem sonuna kadar kümülatif)."""
    if banka_df is None or banka_df.empty:
        return {}
    work = _filter_banka_through_analiz_ayi(banka_df, analiz_ayi)
    if work.empty:
        return {}
    result: dict[str, float] = {}
    used_invoice_amounts: dict[str, float] = {}

    for _, row in work.iterrows():
        if _is_ic_transfer_row(row):
            continue
        tutar = float(row.get("cikis", 0) or 0)
        if tutar <= 0:
            continue
        kod = _resolve_cari_kodu(row)
        prefix = karsi_prefix(kod)

        if prefix == "320" and kod:
            result[kod] = result.get(kod, 0.0) + tutar
            continue

        if prefix == "780":
            continue

        best_kod = ""
        best_diff = float("inf")
        for fkod, info in alis_map.items():
            if not fkod.startswith("320"):
                continue
            already = used_invoice_amounts.get(fkod, 0.0)
            kalan = max(info["tutar"] - already, 0.0)
            if kalan <= 0:
                continue
            diff = abs(kalan - tutar)
            tol = max(kalan, tutar) * TOLERANS_ORAN
            if diff <= max(tol, 1.0) and diff < best_diff:
                best_diff = diff
                best_kod = fkod
        if best_kod:
            result[best_kod] = result.get(best_kod, 0.0) + tutar
            used_invoice_amounts[best_kod] = used_invoice_amounts.get(best_kod, 0.0) + tutar

    return result


def _build_yaslandirma(
    fatura_map: dict[str, dict],
    banka_map: dict[str, float],
) -> list[YaslandirmaSatir]:
    rows: list[YaslandirmaSatir] = []
    for kod, info in sorted(fatura_map.items(), key=lambda x: x[1]["tutar"], reverse=True):
        fatura_tutar = info["tutar"]
        eslesen = banka_map.get(kod, 0.0)
        kalan = max(fatura_tutar - eslesen, 0.0)
        if kalan < 1.0:
            continue
        vade_gun = int(info.get("vade_gun", 0))
        rows.append(
            YaslandirmaSatir(
                cari_kodu=kod,
                cari_adi=info.get("cari_adi", ""),
                fatura_tutari=fatura_tutar,
                eslesen_banka=eslesen,
                kalan=kalan,
                vade_gun=vade_gun,
                bucket=_bucket_for_days(vade_gun),
            )
        )
    return rows


def _muavin_cikis_tutarlari(muavin_df: pd.DataFrame, analiz_ayi: str) -> list[float]:
    """Yalnızca 730/760/770 gider hesaplarındaki borç tutarları (banka çıkış eşleşmesi)."""
    ay = filter_df_by_analiz_ayi(muavin_df, "tarih", analiz_ayi)
    if ay.empty:
        return []
    tutarlar: list[float] = []
    for _, r in ay.iterrows():
        borc = float(r["tl_borc"])
        if borc <= 0:
            continue
        ana = extract_ana_hesap(str(r.get("hesap_kodu", "")))
        if ana in OPEX_ANA_HESAPLAR:
            tutarlar.append(borc)
    return tutarlar


def _tutar_eslesir(a: float, b: float) -> bool:
    if a <= 0 or b <= 0:
        return False
    tol = max(a, b) * TOLERANS_ORAN
    return abs(a - b) <= max(tol, 1.0)


def analyze_yaslandirma(
    satis_fatura_df: pd.DataFrame,
    alis_fatura_df: pd.DataFrame,
    banka_df: pd.DataFrame,
    analiz_ayi: str,
) -> YaslandirmaSonuc:
    satis_map = _fatura_cari_toplam(satis_fatura_df, "120", analiz_ayi)
    alis_map = _fatura_cari_toplam(alis_fatura_df, "320", analiz_ayi)
    tahsilat = _banka_tahsilat_toplam_smart(banka_df, analiz_ayi, satis_map)
    odeme = _banka_odeme_toplam_smart(banka_df, analiz_ayi, alis_map)

    tahsil_edilemeyen = _build_yaslandirma(satis_map, tahsilat)
    odenmeyen = _build_yaslandirma(alis_map, odeme)

    return YaslandirmaSonuc(
        tahsil_edilemeyen=tahsil_edilemeyen,
        odenmeyen=odenmeyen,
        toplam_tahsil_edilemeyen=sum(r.kalan for r in tahsil_edilemeyen),
        toplam_odenmeyen=sum(r.kalan for r in odenmeyen),
    )


def analyze_veri_eslesme(
    muavin_df: pd.DataFrame,
    alis_fatura_df: pd.DataFrame,
    banka_df: pd.DataFrame,
    analiz_ayi: str,
) -> VeriEslesmeSonuc:
    ay_banka = filter_df_by_analiz_ayi(banka_df, "tarih", analiz_ayi)
    if ay_banka.empty:
        return VeriEslesmeSonuc(yorum="Banka verisi yok.")

    muavin_tutarlar = _muavin_cikis_tutarlari(muavin_df, analiz_ayi)
    alis_map = _fatura_cari_toplam(alis_fatura_df, "320", analiz_ayi, include_prior_open=True)

    eslesen = 0.0
    toplam_cikis = 0.0
    ic_transfer = 0.0
    vergi_cikis = 0.0
    aciklanamayan: list[AciklanamayanGider] = []
    used_muavin: set[int] = set()
    used_fatura_kod: set[str] = set()

    for _, row in ay_banka.iterrows():
        tutar = float(row.get("cikis", 0) or 0)
        if tutar <= 0:
            continue

        kod = _resolve_cari_kodu(row)
        prefix = karsi_prefix(kod)

        if _is_ic_transfer_row(row):
            ic_transfer += tutar
            continue

        toplam_cikis += tutar
        matched = False

        if prefix == "780":
            vergi_cikis += tutar
            eslesen += tutar
            continue

        if prefix == "320" and kod in alis_map:
            eslesen += tutar
            used_fatura_kod.add(kod)
            continue

        for idx, mt in enumerate(muavin_tutarlar):
            if idx in used_muavin:
                continue
            if _tutar_eslesir(tutar, mt):
                used_muavin.add(idx)
                matched = True
                eslesen += tutar
                break

        if not matched:
            for fkod, info in alis_map.items():
                if fkod in used_fatura_kod:
                    continue
                if _tutar_eslesir(tutar, info["tutar"]):
                    used_fatura_kod.add(fkod)
                    matched = True
                    eslesen += tutar
                    break

        if not matched:
            tarih = row["tarih"]
            tarih_str = tarih.strftime("%d.%m.%Y") if pd.notna(tarih) else ""
            kategori = "vergi" if prefix == "780" else "kayit_disi"
            aciklanamayan.append(
                AciklanamayanGider(
                    tarih=tarih_str,
                    aciklama=str(row.get("aciklama", "")),
                    tutar=tutar,
                    banka_adi=str(row.get("banka_adi", "")),
                    cari_kodu=kod,
                    kategori=kategori,
                )
            )

    skor = (eslesen / toplam_cikis * 100) if toplam_cikis > 0 else 100.0
    yorum = (
        f"Veri eşleşme skoru %{skor:.1f} "
        f"({format_tl(eslesen)} / {format_tl(toplam_cikis)}; 102 transfer hariç)."
    )
    if ic_transfer > 0:
        yorum += f" İç transfer (102) çıkış: {format_tl(ic_transfer)}."
    if vergi_cikis > 0:
        yorum += f" Vergi/SGK (780) çıkış: {format_tl(vergi_cikis)}."
    if aciklanamayan:
        yorum += f" {len(aciklanamayan)} kayıt dışı çıkış listelendi."

    return VeriEslesmeSonuc(
        eslesme_skoru_pct=skor,
        toplam_banka_cikis=toplam_cikis,
        eslesen_banka_cikis=eslesen,
        ic_transfer_cikis=ic_transfer,
        vergi_odeme_cikis=vergi_cikis,
        aciklanamayan_giderler=aciklanamayan,
        yorum=yorum,
    )


def analyze_reconciliation(
    muavin_df: pd.DataFrame,
    alis_fatura_df: pd.DataFrame,
    satis_fatura_df: pd.DataFrame,
    banka_df: pd.DataFrame,
    analiz_ayi: str,
) -> tuple[YaslandirmaSonuc, VeriEslesmeSonuc]:
    yas = analyze_yaslandirma(satis_fatura_df, alis_fatura_df, banka_df, analiz_ayi)
    eslesme = analyze_veri_eslesme(muavin_df, alis_fatura_df, banka_df, analiz_ayi)
    return yas, eslesme
