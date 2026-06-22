"""
Mikro banka ekstresi dosyalarını okur ve tek nakit havuzunda birleştirir.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from parse_utils import MizanParseError, karsi_prefix, normalize_header, parse_turkish_amount

STANDARD_BANK_COLUMNS = [
    "tarih",
    "evrak_tipi",
    "aciklama",
    "giris",
    "cikis",
    "bakiye",
    "cari_kodu",
    "karsi_hesap_prefix",
    "banka_adi",
    "ic_transfer",
]

MIKRO_BANK_COLUMN_MAP: dict[str, str] = {
    "tarih": "tarih",
    "evrak tipi": "evrak_tipi",
    "evrak_tipi": "evrak_tipi",
    "ana diviz borc": "tl_borc",
    "ana diviz borç": "tl_borc",
    "ana doviz borc": "tl_borc",
    "ana döviz borç": "tl_borc",
    "ana diviz alacak": "tl_alacak",
    "ana doviz alacak": "tl_alacak",
    "ana döviz alacak": "tl_alacak",
    "ana diviz borc bakiye": "borc_bakiye",
    "ana diviz borç bakiye": "borc_bakiye",
    "ana doviz borc bakiye": "borc_bakiye",
    "ana döviz borç bakiye": "borc_bakiye",
    "ana diviz alacak bakiye": "alacak_bakiye",
    "ana doviz alacak bakiye": "alacak_bakiye",
    "ana döviz alacak bakiye": "alacak_bakiye",
    "karsi hesap kodu": "cari_kodu",
    "karşı hesap kodu": "cari_kodu",
    "karsi hesap ismi": "karsi_hesap_ismi",
    "karşı hesap ismi": "karsi_hesap_ismi",
}

MIKRO_BORC_HEADERS = (
    "ANA DİVİZ BORÇ", "ANA DIVIZ BORC",
    "ANA DÖVİZ BORÇ", "ANA DOVIZ BORC",
)
MIKRO_ALACAK_HEADERS = (
    "ANA DİVİZ ALACAK", "ANA DIVIZ ALACAK",
    "ANA DÖVİZ ALACAK", "ANA DOVIZ ALACAK",
)

CARI_CODE_PATTERN = re.compile(r"\b(1[02]0\.\d{3,}|3[02]0\.\d{3,}|780\.\d{2,})\b")


class BankParseError(MizanParseError):
    """Banka dosyası okuma hatası."""


def _find_column(columns: list[str], *candidates: str) -> str | None:
    normalized = {normalize_header(c): c for c in columns}
    for cand in candidates:
        key = normalize_header(cand)
        if key in normalized:
            return normalized[key]
    for col in columns:
        norm = normalize_header(col)
        for cand in candidates:
            if normalize_header(cand) in norm:
                return col
    return None


def _is_mikro_bank_columns(columns: list[str]) -> bool:
    return _find_column(columns, *MIKRO_BORC_HEADERS) is not None


def _map_mikro_columns(raw: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    for col in raw.columns:
        key = normalize_header(str(col))
        if key in MIKRO_BANK_COLUMN_MAP:
            rename[col] = MIKRO_BANK_COLUMN_MAP[key]
    if "tarih" not in rename.values():
        tarih_col = _find_column(list(raw.columns), "TARİH", "TARIH")
        if tarih_col:
            rename[tarih_col] = "tarih"
    if "tl_borc" not in rename.values():
        borc = _find_column(list(raw.columns), *MIKRO_BORC_HEADERS)
        if borc:
            rename[borc] = "tl_borc"
    if "tl_alacak" not in rename.values():
        alacak = _find_column(list(raw.columns), *MIKRO_ALACAK_HEADERS)
        if alacak:
            rename[alacak] = "tl_alacak"
    if "cari_kodu" not in rename.values():
        cari = _find_column(list(raw.columns), "KARŞI HESAP KODU", "KARSI HESAP KODU")
        if cari:
            rename[cari] = "cari_kodu"
    if "karsi_hesap_ismi" not in rename.values():
        isim = _find_column(list(raw.columns), "KARŞI HESAP İSMİ", "KARSI HESAP ISMI")
        if isim:
            rename[isim] = "karsi_hesap_ismi"
    if "evrak_tipi" not in rename.values():
        evrak = _find_column(list(raw.columns), "EVRAK TİPİ", "EVRAK TIPI")
        if evrak:
            rename[evrak] = "evrak_tipi"
    for src, dst in (
        (_find_column(list(raw.columns), "ANA DİVİZ BORÇ BAKİYE", "ANA DÖVİZ BORÇ BAKİYE", "ANA DOVIZ BORC BAKIYE"), "borc_bakiye"),
        (_find_column(list(raw.columns), "ANA DİVİZ ALACAK BAKİYE", "ANA DÖVİZ ALACAK BAKİYE", "ANA DOVIZ ALACAK BAKIYE"), "alacak_bakiye"),
    ):
        if src and dst not in rename.values():
            rename[src] = dst
    return raw.rename(columns=rename)


def _net_bakiye_row(borc_bakiye: object, alacak_bakiye: object) -> float:
    bb = parse_turkish_amount(borc_bakiye) if pd.notna(borc_bakiye) else 0.0
    ab = parse_turkish_amount(alacak_bakiye) if pd.notna(alacak_bakiye) else 0.0
    if bb != 0:
        return bb
    if ab != 0:
        return -ab
    return 0.0


def _coerce_mikro_bank_frame(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    if "tarih" not in df.columns:
        raise BankParseError("Mikro banka dosyasında TARİH sütunu bulunamadı.")

    banka_adi = path.stem
    records: list[dict] = []
    for _, row in df.iterrows():
        tarih = pd.to_datetime(row.get("tarih"), errors="coerce", dayfirst=True)
        if pd.isna(tarih):
            continue

        borc = parse_turkish_amount(row.get("tl_borc", 0))
        alacak = parse_turkish_amount(row.get("tl_alacak", 0))
        cari = str(row.get("cari_kodu", "")).strip()
        if cari in ("nan", "None"):
            cari = ""
        evrak = str(row.get("evrak_tipi", "")).strip()
        isim = str(row.get("karsi_hesap_ismi", "")).strip()
        if isim in ("nan", "None"):
            isim = ""
        aciklama = " — ".join(p for p in (evrak, isim) if p)
        prefix = karsi_prefix(cari)
        ic_transfer = prefix == "102"

        records.append({
            "tarih": tarih,
            "evrak_tipi": evrak,
            "aciklama": aciklama,
            "giris": borc,
            "cikis": alacak,
            "bakiye": _net_bakiye_row(row.get("borc_bakiye"), row.get("alacak_bakiye")),
            "cari_kodu": cari,
            "karsi_hesap_prefix": prefix,
            "banka_adi": banka_adi,
            "ic_transfer": ic_transfer,
        })

    if not records:
        raise BankParseError("Banka dosyasında işlenecek hareket satırı bulunamadı.")

    out = pd.DataFrame(records)
    out = out[
        (out["giris"] != 0) | (out["cikis"] != 0) | (out["bakiye"] != 0)
    ].copy()
    return out[STANDARD_BANK_COLUMNS].copy()


def _read_mikro_bank_excel(path: Path) -> pd.DataFrame:
    try:
        raw = pd.read_excel(path, sheet_name=0)
    except Exception as exc:
        raise BankParseError(f"Excel okunamadı: {exc}") from exc
    if raw.empty:
        raise BankParseError("Banka dosyası boş.")
    if not _is_mikro_bank_columns(list(raw.columns)):
        raise BankParseError(
            "Tanınmayan banka formatı. Mikro banka ekstresi (ANA DİVİZ BORÇ/ALACAK) bekleniyor."
        )
    mapped = _map_mikro_columns(raw)
    return _coerce_mikro_bank_frame(mapped, path)


def load_banka_dosyasi(path: Path | str, banka_adi: str = "") -> pd.DataFrame:
    """Tek Mikro banka ekstresi dosyasını yükler."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise BankParseError("Banka dosyası .xlsx veya .csv formatında olmalı.")

    try:
        if suffix == ".csv":
            raw = pd.read_csv(file_path, encoding="utf-8-sig", sep=";")
            if raw.shape[1] == 1:
                raw = pd.read_csv(file_path, encoding="utf-8-sig")
            if not _is_mikro_bank_columns(list(raw.columns)):
                raise BankParseError("CSV banka formatı tanınmadı.")
            df = _coerce_mikro_bank_frame(_map_mikro_columns(raw), file_path)
        else:
            df = _read_mikro_bank_excel(file_path)
    except (BankParseError, FileNotFoundError):
        raise
    except Exception as exc:
        raise BankParseError(f"Banka dosyası okunurken hata: {exc}") from exc

    if banka_adi:
        df["banka_adi"] = banka_adi
    return df


def load_banka_dosyalari(
    paths: list[Path | str],
    banka_adlari: list[str] | None = None,
) -> pd.DataFrame:
    """Birden fazla banka dosyasını tek havuzda birleştirir."""
    if not paths:
        return pd.DataFrame(columns=STANDARD_BANK_COLUMNS)
    frames: list[pd.DataFrame] = []
    for idx, p in enumerate(paths):
        ad = ""
        if banka_adlari and idx < len(banka_adlari):
            ad = banka_adlari[idx]
        frames.append(load_banka_dosyasi(p, ad))
    return pd.concat(frames, ignore_index=True).sort_values("tarih").reset_index(drop=True)
