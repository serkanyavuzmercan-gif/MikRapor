"""
Ay bazlı muavin defteri dosyalarını okur (Mikro Excel/CSV export).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from parse_utils import (
    MizanParseError,
    MissingColumnError,
    extract_ana_hesap,
    is_alt_hesap,
    load_tabular_file,
    normalize_hesap_kodu,
    parse_turkish_amount,
)

MUAVIN_COLUMN_ALIASES: dict[str, str] = {
    "tarih": "tarih",
    "fis tarihi": "tarih",
    "fiş tarihi": "tarih",
    "hesap kodu": "hesap_kodu",
    "hesap_kodu": "hesap_kodu",
    "hesap adi": "hesap_adi",
    "hesap adı": "hesap_adi",
    "hesap_adi": "hesap_adi",
    "borc": "tl_borc",
    "borç": "tl_borc",
    "tl borc": "tl_borc",
    "tl borç": "tl_borc",
    "alacak": "tl_alacak",
    "tl alacak": "tl_alacak",
    "aciklama": "aciklama",
    "açıklama": "aciklama",
    "satir aciklamasi": "aciklama",
    "satır açıklaması": "aciklama",
    "cari kodu": "cari_kodu",
    "cari_kodu": "cari_kodu",
    "evrak no": "evrak_no",
    "evrak_no": "evrak_no",
    "fis no": "evrak_no",
    "fiş no": "evrak_no",
}

REQUIRED_MUAVIN_COLUMNS = {"tarih", "hesap_kodu", "tl_borc", "tl_alacak"}
NUMERIC_MUAVIN_COLUMNS = {"tl_borc", "tl_alacak"}

STANDARD_MUAVIN_COLUMNS = [
    "tarih",
    "hesap_kodu",
    "hesap_adi",
    "tl_borc",
    "tl_alacak",
    "aciklama",
    "cari_kodu",
    "evrak_no",
    "ana_hesap",
    "alt_hesap",
]


class MuavinParseError(MizanParseError):
    """Muavin dosyası okuma hatası."""


def _coerce_muavin_frame(df: pd.DataFrame, path: Path) -> pd.DataFrame:
  del path
  if "hesap_adi" not in df.columns:
      df["hesap_adi"] = ""
  for col in ("aciklama", "cari_kodu", "evrak_no"):
      if col not in df.columns:
          df[col] = ""
      else:
          df[col] = df[col].astype(str).str.strip()
          df.loc[df[col].isin(["nan", "None"]), col] = ""

  df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce", dayfirst=True)
  df["hesap_kodu"] = df["hesap_kodu"].apply(normalize_hesap_kodu)
  df["hesap_adi"] = df["hesap_adi"].astype(str).str.strip()
  df["ana_hesap"] = df["hesap_kodu"].apply(extract_ana_hesap)
  df["alt_hesap"] = df["hesap_kodu"].apply(is_alt_hesap)

  df = df[
      (df["hesap_kodu"] != "")
      & (df["tarih"].notna())
      & ((df["tl_borc"] != 0) | (df["tl_alacak"] != 0))
  ].copy()

  if df.empty:
      raise MuavinParseError("Muavin dosyasında işlenecek hareket satırı bulunamadı.")

  return df[STANDARD_MUAVIN_COLUMNS].copy()


def load_muavin(path: Path | str) -> pd.DataFrame:
    """Tek muavin dosyasını yükler."""
    return load_tabular_file(
        path,
        MUAVIN_COLUMN_ALIASES,
        required=REQUIRED_MUAVIN_COLUMNS,
        numeric_cols=NUMERIC_MUAVIN_COLUMNS,
        coerce=_coerce_muavin_frame,
    )


def load_muavin_files(paths: list[Path | str]) -> pd.DataFrame:
    """Birden fazla muavin dosyasını birleştirir."""
    if not paths:
        raise MuavinParseError("Muavin dosyası seçilmedi.")
    frames = [load_muavin(p) for p in paths]
    return pd.concat(frames, ignore_index=True)


def validate_muavin_month_range(df: pd.DataFrame, analiz_ayi: str) -> list[str]:
    """Yüklenen muavin tarih aralığının analiz ayı ile uyumunu kontrol eder."""
    from period_utils import analiz_ayi_araligi

    if df.empty or not analiz_ayi:
        return []
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    min_t = df["tarih"].min()
    max_t = df["tarih"].max()
    warnings: list[str] = []
    if pd.notna(min_t) and min_t.date() < bas:
        warnings.append(
            f"Muavin dosyasında analiz ayından önce kayıt var ({min_t.date()})."
        )
    if pd.notna(max_t) and max_t.date() > bit:
        warnings.append(
            f"Muavin dosyasında analiz ayından sonra kayıt var ({max_t.date()})."
        )
    return warnings
