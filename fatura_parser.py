"""
Alış ve satış fatura dökümü Excel dosyalarını okur.

ERP çıktılarında fatura başlık satırları ve boş ayraç satırları filtrelenir;
yalnızca stok kodu dolu detay satırları işlenir.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd

from parse_utils import MizanParseError, MissingColumnError, parse_turkish_amount

FaturaTuru = Literal["alis", "satis"]

FATURA_COLUMN_ALIASES: dict[str, str] = {
    "fatura no": "fatura_no",
    "fatura_no": "fatura_no",
    "belge no": "belge_no",
    "belge_no": "belge_no",
    "cins": "cins",
    "tarih": "tarih",
    "vade": "vade",
    "cari kodu": "cari_kodu",
    "cari_kodu": "cari_kodu",
    "cari adi": "cari_adi",
    "cari adı": "cari_adi",
    "cari_adi": "cari_adi",
    "miktar": "miktar",
    "brut br.fiy": "brut_bf",
    "brüt br.fiy": "brut_bf",
    "net br.fiy": "net_bf",
    "net tutar": "net_tutar",
    "stok dvz": "stok_dvz",
    "stok kur": "stok_kur",
    "toplam": "toplam",
    "gib fatura no": "gib_fatura_no",
}

STOK_KODU_PATTERNS = (
    "stok/hizmet/masraf/ demirbas/ithalat kodu",
    "stok/hizmet/masraf/ demirbaş/ithalat kodu",
    "stok/hizmet/masraf/demirbas/ithalat kodu",
    "stok/hizmet/masraf/demirbaş/ithalat kodu",
)

STOK_ADI_PATTERNS = (
    "stok/hizmet/masraf/ demirbas/ithalat ismi",
    "stok/hizmet/masraf/ demirbaş/ithalat ismi",
    "stok/hizmet/masraf/demirbas/ithalat ismi",
    "stok/hizmet/masraf/demirbaş/ithalat ismi",
)

REQUIRED_FATURA_COLUMNS = {"stok_kodu", "miktar", "net_tutar"}

STANDARD_FATURA_COLUMNS = [
    "fatura_no",
    "belge_no",
    "cins",
    "tarih",
    "vade",
    "cari_kodu",
    "cari_adi",
    "stok_kodu",
    "stok_adi",
    "miktar",
    "net_bf",
    "net_tutar",
    "stok_dvz",
    "fatura_turu",
    "dokum_tarihi",
    "kaynak_dosya",
    "kaynak_ay",
]

FILENAME_AY_PATTERN = re.compile(r"(\d{2})(\d{4})")


class FaturaParseError(MizanParseError):
    """Alış/satış fatura dosyası okuma hatası."""


def _normalize_header(name: object) -> str:
    text = str(name).replace("İ", "i").replace("I", "i")
    text = text.strip().lower()
    text = text.replace("ı", "i").replace("ğ", "g").replace("ü", "u")
    text = text.replace("ş", "s").replace("ö", "o").replace("ç", "c")
    text = text.replace("\u0307", "")
    text = re.sub(r"\s+", " ", text)
    return text


def _map_columns(raw_columns: list[object]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for col in raw_columns:
        key = _normalize_header(col)
        if key in FATURA_COLUMN_ALIASES:
            mapping[str(col)] = FATURA_COLUMN_ALIASES[key]
        elif key in STOK_KODU_PATTERNS:
            mapping[str(col)] = "stok_kodu"
        elif key in STOK_ADI_PATTERNS:
            mapping[str(col)] = "stok_adi"
    return mapping


def infer_ay_from_filename(stem: str) -> str | None:
    """'Alış 032026' veya 'Satış 052026' -> '2026-03'."""
    text = stem.replace("İ", "i").replace("ı", "i").replace("ş", "s").lower()
    match = FILENAME_AY_PATTERN.search(text)
    if not match:
        return None
    month, year = int(match.group(1)), int(match.group(2))
    if month < 1 or month > 12:
        return None
    return f"{year:04d}-{month:02d}"


def infer_fatura_dokum_tarihi(filename: str) -> str:
    """Dosya adından döküm tarihini çıkarır (ör. 11.06.2026)."""
    match = re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})", filename)
    return match.group(1) if match else ""


def _read_excel_fatura(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    for candidate in xl.sheet_names:
        hint = _normalize_header(candidate)
        if "fatura" in hint or "alis" in hint or "satis" in hint or "satış" in hint:
            sheet = candidate
            break
    df = pd.read_excel(path, sheet_name=sheet)
    df.attrs["sheet_name"] = sheet
    return df


def _detect_fatura_turu(
    df: pd.DataFrame,
    path: Path,
    expected: FaturaTuru | None,
) -> FaturaTuru:
    if expected:
        return expected

    name = path.name.lower()
    sheet_hint = ""
    if hasattr(df, "attrs") and df.attrs.get("sheet_name"):
        sheet_hint = str(df.attrs["sheet_name"]).lower()
    combined = f"{name} {sheet_hint}"

    if "alis" in combined or "alış" in combined:
        return "alis"
    if "satis" in combined or "satış" in combined:
        return "satis"

    if "cari_kodu" in df.columns:
        codes = df["cari_kodu"].astype(str).str.strip()
        if codes.str.startswith("320").any():
            return "alis"
        if codes.str.startswith("120").any():
            return "satis"

    raise FaturaParseError(
        "Dosya türü belirlenemedi. Alış veya satış fatura dökümü seçin."
    )


def _coerce_fatura_frame(
    raw: pd.DataFrame,
    path: Path,
    expected: FaturaTuru | None,
) -> pd.DataFrame:
    rename_map = _map_columns(list(raw.columns))
    if "stok_kodu" not in rename_map.values():
        for col in raw.columns:
            norm = _normalize_header(col)
            if "stok" in norm and "kodu" in norm:
                rename_map[str(col)] = "stok_kodu"
            elif "stok" in norm and "ismi" in norm:
                rename_map[str(col)] = "stok_adi"

    if not rename_map:
        raise FaturaParseError("Tanınan sütun başlığı bulunamadı.")

    df = raw.rename(columns=rename_map).copy()
    missing = REQUIRED_FATURA_COLUMNS - set(df.columns)
    if missing:
        raise MissingColumnError(sorted(missing))

    fatura_turu = _detect_fatura_turu(df, path, expected)
    df["fatura_turu"] = fatura_turu
    df["dokum_tarihi"] = infer_fatura_dokum_tarihi(path.stem)
    df["kaynak_dosya"] = path.name
    df["kaynak_ay"] = infer_ay_from_filename(path.stem) or ""

    for col in ("fatura_no", "belge_no", "cins", "cari_kodu", "cari_adi", "stok_kodu", "stok_adi"):
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["nan", "None"]), col] = ""

    for col in ("tarih", "vade"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        else:
            df[col] = pd.NaT

    if "net_bf" not in df.columns:
        df["net_bf"] = 0.0
    else:
        df["net_bf"] = df["net_bf"].apply(parse_turkish_amount)

    df["miktar"] = pd.to_numeric(df["miktar"], errors="coerce").fillna(0.0)
    df["net_tutar"] = df["net_tutar"].apply(parse_turkish_amount)

    if "stok_dvz" not in df.columns:
        df["stok_dvz"] = "TL"

    # Yalnızca stok detay satırları
    df = df[
        (df["stok_kodu"] != "")
        & (df["miktar"] > 0)
        & (df["net_tutar"] != 0)
    ].copy()

    if df.empty:
        raise FaturaParseError("Fatura dosyasında işlenecek stok detay satırı bulunamadı.")

    for col in STANDARD_FATURA_COLUMNS:
        if col not in df.columns:
            if col in {"fatura_no", "belge_no", "cins", "cari_kodu", "cari_adi", "stok_kodu", "stok_adi",
                       "stok_dvz", "fatura_turu", "dokum_tarihi", "kaynak_dosya", "kaynak_ay"}:
                df[col] = ""
            elif col in {"tarih", "vade"}:
                df[col] = pd.NaT
            else:
                df[col] = 0.0

    return df[STANDARD_FATURA_COLUMNS].copy()


def load_fatura(path: Path | str, expected: FaturaTuru | None = None) -> pd.DataFrame:
    """Alış veya satış fatura döküm Excel dosyasını yükler."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        raise FaturaParseError("Fatura dosyası yalnızca Excel (.xlsx) formatında desteklenir.")

    try:
        raw = _read_excel_fatura(file_path)
    except Exception as exc:
        raise FaturaParseError(f"Excel okunamadı: {exc}") from exc

    if raw.empty:
        raise FaturaParseError("Fatura dosyası boş.")

    return _coerce_fatura_frame(raw, file_path, expected)


def load_alis_faturalari(path: Path | str) -> pd.DataFrame:
    return load_fatura(path, expected="alis")


def load_satis_faturalari(path: Path | str) -> pd.DataFrame:
    return load_fatura(path, expected="satis")


def load_alis_faturalari_dosyalari(paths: list[Path | str]) -> pd.DataFrame:
    """Birden fazla aylık alış fatura dosyasını birleştirir."""
    if not paths:
        return pd.DataFrame(columns=STANDARD_FATURA_COLUMNS)
    frames = [load_alis_faturalari(p) for p in paths]
    return pd.concat(frames, ignore_index=True)


def load_satis_faturalari_dosyalari(paths: list[Path | str]) -> pd.DataFrame:
    """Birden fazla aylık satış fatura dosyasını birleştirir."""
    if not paths:
        return pd.DataFrame(columns=STANDARD_FATURA_COLUMNS)
    frames = [load_satis_faturalari(p) for p in paths]
    return pd.concat(frames, ignore_index=True)
