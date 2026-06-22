"""
120 tahsilat ve 320 tediye (ödeme) planı Excel dosyalarını okur.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd

from parse_utils import MizanParseError, MissingColumnError, normalize_header, parse_turkish_amount

PlanTuru = Literal["tahsilat", "tediye"]

CARI_PLAN_COLUMN_ALIASES: dict[str, str] = {
    "hesap kodu": "hesap_kodu",
    "hesap_kodu": "hesap_kodu",
    "hesapkodu": "hesap_kodu",
    "hesap adi": "hesap_adi",
    "hesap adı": "hesap_adi",
    "hesap_adi": "hesap_adi",
    "meblag": "meblag",
    "meblağ": "meblag",
    "satir bakiye": "satir_bakiye",
    "satır bakiye": "satir_bakiye",
    "vade tarih": "vade_tarih",
    "vade gun": "vade_gun",
    "vade gün": "vade_gun",
}

SUMMARY_ROW_MARKERS = ("ortalama", "gruplar toplami", "gruplar toplamı", "toplam")

STANDARD_PLAN_COLUMNS = [
    "hesap_kodu",
    "hesap_adi",
    "meblag",
    "satir_bakiye",
    "vade_kalan_gun",
    "vade_tarih",
    "plan_turu",
    "rapor_referans_tarihi",
]

VADE_ICIN_PATTERN = re.compile(r"icin vade|için vade", re.IGNORECASE)


class CariPlanParseError(MizanParseError):
    """Tahsilat/tediye plan dosyası okuma hatası."""


def _map_columns(raw_columns: list[object]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for col in raw_columns:
        key = normalize_header(str(col))
        if key in CARI_PLAN_COLUMN_ALIASES:
            mapping[str(col)] = CARI_PLAN_COLUMN_ALIASES[key]
    return mapping


def _find_dynamic_vade_column(columns: list[str]) -> str | None:
    for col in columns:
        if VADE_ICIN_PATTERN.search(str(col)):
            return col
    return None


def _extract_referans_tarihi(vade_col: str) -> str:
    match = re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})", vade_col)
    return match.group(1) if match else ""


def _is_summary_row(hesap_kodu: str, hesap_adi: str) -> bool:
    kod = hesap_kodu.strip().lower()
    ad = hesap_adi.strip().lower()
    if not kod or kod in ("nan", "none"):
        return True
    for marker in SUMMARY_ROW_MARKERS:
        if marker in kod or marker in ad:
            return True
    return False


def _coerce_plan_frame(
    raw: pd.DataFrame,
    path: Path,
    plan_turu: PlanTuru,
) -> pd.DataFrame:
    rename_map = _map_columns(list(raw.columns))
    vade_col = _find_dynamic_vade_column(list(raw.columns))
    if vade_col:
        rename_map[vade_col] = "vade_kalan_gun"
    if not rename_map:
        raise CariPlanParseError("Tanınan sütun başlığı bulunamadı.")

    df = raw.rename(columns=rename_map).copy()
    required = {"hesap_kodu", "meblag"}
    missing = required - set(df.columns)
    if missing:
        raise MissingColumnError(sorted(missing))

    if "satir_bakiye" not in df.columns:
        df["satir_bakiye"] = df["meblag"]
    if "hesap_adi" not in df.columns:
        df["hesap_adi"] = ""
    if "vade_tarih" not in df.columns:
        df["vade_tarih"] = pd.NaT

    df["hesap_kodu"] = df["hesap_kodu"].astype(str).str.strip()
    df["hesap_adi"] = df["hesap_adi"].astype(str).str.strip()
    df.loc[df["hesap_kodu"].isin(["nan", "None"]), "hesap_kodu"] = ""
    df.loc[df["hesap_adi"].isin(["nan", "None"]), "hesap_adi"] = ""

    df = df[
        ~df.apply(
            lambda r: _is_summary_row(str(r["hesap_kodu"]), str(r["hesap_adi"])),
            axis=1,
        )
    ].copy()

    prefix = "120" if plan_turu == "tahsilat" else "320"
    df = df[df["hesap_kodu"].str.startswith(prefix)].copy()

    df["meblag"] = df["meblag"].apply(parse_turkish_amount)
    df["satir_bakiye"] = df["satir_bakiye"].apply(parse_turkish_amount)
    df["vade_kalan_gun"] = pd.to_numeric(
        df.get("vade_kalan_gun", 0), errors="coerce"
    ).fillna(0.0)

    if "vade_tarih" in df.columns:
        df["vade_tarih"] = pd.to_datetime(df["vade_tarih"], errors="coerce", dayfirst=True)

    df = df[df["meblag"] != 0].copy()
    if df.empty:
        raise CariPlanParseError("Plan dosyasında işlenecek satır bulunamadı.")

    df["plan_turu"] = plan_turu
    df["rapor_referans_tarihi"] = _extract_referans_tarihi(vade_col or "")

    for col in STANDARD_PLAN_COLUMNS:
        if col not in df.columns:
            if col in ("hesap_kodu", "hesap_adi", "plan_turu", "rapor_referans_tarihi"):
                df[col] = ""
            elif col == "vade_tarih":
                df[col] = pd.NaT
            else:
                df[col] = 0.0

    return df[STANDARD_PLAN_COLUMNS].copy()


def load_cari_plan(path: Path | str, plan_turu: PlanTuru) -> pd.DataFrame:
    """120 tahsilat veya 320 tediye plan Excel dosyasını yükler."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    if file_path.suffix.lower() not in {".xlsx", ".xls"}:
        raise CariPlanParseError("Plan dosyası yalnızca Excel (.xlsx) formatında desteklenir.")
    try:
        raw = pd.read_excel(file_path, sheet_name=0)
    except Exception as exc:
        raise CariPlanParseError(f"Excel okunamadı: {exc}") from exc
    if raw.empty:
        raise CariPlanParseError("Plan dosyası boş.")
    return _coerce_plan_frame(raw, file_path, plan_turu)


def load_tahsilat_plan(path: Path | str) -> pd.DataFrame:
    return load_cari_plan(path, "tahsilat")


def load_tediye_plan(path: Path | str) -> pd.DataFrame:
    return load_cari_plan(path, "tediye")
