"""
Paylaşılan dosya okuma, sayı temizleme ve hesap kodu normalizasyonu.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

# --- İstisnalar ---


class MizanParseError(Exception):
    """Dosya okuma veya doğrulama hatası."""


class MissingColumnError(MizanParseError):
    """Zorunlu sütun eksik."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        names = ", ".join(missing)
        super().__init__(f"Zorunlu sütunlar bulunamadı: {names}")


def normalize_header(text: str) -> str:
    """Başlık metnini karşılaştırma için normalize eder."""
    raw = str(text).replace("İ", "i").replace("I", "i")
    raw = raw.strip().lower()
    raw = raw.replace("ı", "i").replace("ğ", "g").replace("ü", "u")
    raw = raw.replace("ş", "s").replace("ö", "o").replace("ç", "c")
    raw = raw.replace("\u0307", "")
    return re.sub(r"\s+", " ", raw.replace("_", " "))


def map_headers(headers: list[str], aliases: dict[str, str]) -> dict[int, str]:
    """Ham başlık listesini standart sütun adlarına eşler."""
    mapping: dict[int, str] = {}
    for idx, header in enumerate(headers):
        key = normalize_header(header)
        if key in aliases:
            mapping[idx] = aliases[key]
    return mapping


def parse_turkish_amount(value: object) -> float:
    """
    Türkçe/uluslararası sayı formatlarını float'a çevirir.

    Örnekler:
        1.234.567,89  -> 1234567.89
        1,234,567.89  -> 1234567.89
        50 000,00     -> 50000.0
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "-"):
        return 0.0

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    text = text.replace(" ", "").replace("\u00a0", "")
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in (".", ",", "-"):
        return 0.0

    if "," in text and "." in text:
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")
        if last_comma > last_dot:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            text = parts[0].replace(".", "") + "." + parts[1]
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            pass
        else:
            text = text.replace(".", "")

    try:
        result = float(text)
    except ValueError as exc:
        raise MizanParseError(f"Sayısal değer okunamadı: {value!r}") from exc

    return -result if negative else result


def format_tl(amount: float) -> str:
    """Tutarı Türkçe binlik ayraçlı TL formatında döndürür."""
    text = f"{abs(amount):,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "-" if amount < 0 else ""
    return f"{prefix}{text} TL"


def normalize_hesap_kodu(kod: object) -> str:
    """Hesap kodunu standart string biçimine getirir."""
    if kod is None or (isinstance(kod, float) and pd.isna(kod)):
        return ""
    text = str(kod).strip().replace(" ", "")
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text


def extract_ana_hesap(kod: str) -> str:
    """3 haneli ana hesap kodunu çıkarır (örn. 102.01 -> 102)."""
    kod = normalize_hesap_kodu(kod)
    if not kod:
        return ""
    if "." in kod:
        return kod.split(".")[0]
    if len(kod) >= 3:
        return kod[:3]
    return kod.zfill(3)


def is_alt_hesap(kod: str) -> bool:
    """Hesap kodunun alt kırılım olup olmadığını belirler."""
    return "." in normalize_hesap_kodu(kod)


def karsi_prefix(kod: str) -> str:
    """Karşı hesap kodundan ana prefix döndürür (örn. 120.01.001 -> 120)."""
    kod = str(kod).strip()
    if not kod or kod in ("nan", "None"):
        return ""
    if "." in kod:
        return kod.split(".")[0]
    return kod[:3] if len(kod) >= 3 else kod


def read_tabular_raw(path: Path) -> tuple[list[str], list[list[object]]]:
    """CSV veya Excel dosyasından ham başlık ve satırları okur."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw_text = path.read_text(encoding="utf-8-sig")
        if not raw_text.strip():
            raise MizanParseError("CSV dosyası boş.")
        try:
            dialect = csv.Sniffer().sniff(raw_text[:4096], delimiters=";,\t")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";" if ";" in raw_text.splitlines()[0] else ","
        rows: list[list[object]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh, delimiter=delimiter)
            headers = next(reader, None)
            if not headers:
                raise MizanParseError("CSV dosyasında başlık satırı yok.")
            for line in reader:
                rows.append(line)
        return [str(h) for h in headers], rows

    if suffix in (".xlsx", ".xlsm", ".xls"):
        try:
            df = pd.read_excel(path)
        except Exception as exc:
            raise MizanParseError(f"Excel okunamadı: {exc}") from exc
        if df.empty:
            raise MizanParseError("Excel dosyası boş.")
        headers = [str(c) for c in df.columns]
        rows = [list(row) for row in df.itertuples(index=False, name=None)]
        return headers, rows

    raise MizanParseError("Desteklenen formatlar: .xlsx, .xls, .csv")


def rows_to_dataframe(
    rows: list[list[object]],
    mapping: dict[int, str],
    *,
    required: set[str],
    numeric_cols: set[str] | None = None,
    empty_message: str = "Dosyada geçerli satır bulunamadı.",
    row_filter: callable | None = None,
) -> pd.DataFrame:
    """Ham satırları standart DataFrame'e dönüştürür."""
    records: list[dict[str, object]] = []
    for row in rows:
        if not any(cell is not None and str(cell).strip() for cell in row):
            continue
        record: dict[str, object] = {}
        for idx, col in mapping.items():
            if idx < len(row):
                record[col] = row[idx]
        if row_filter and not row_filter(record):
            continue
        if record:
            records.append(record)

    if not records:
        raise MizanParseError(empty_message)

    df = pd.DataFrame(records)
    missing = required - set(df.columns)
    if missing:
        raise MissingColumnError(sorted(missing))

    if numeric_cols:
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = df[col].apply(parse_turkish_amount)

    return df


def load_tabular_file(
    path: Path | str,
    aliases: dict[str, str],
    *,
    required: set[str],
    numeric_cols: set[str] | None = None,
    coerce: callable,
) -> pd.DataFrame:
    """Genel tablo dosyası yükleyici."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    try:
        headers, rows = read_tabular_raw(file_path)
        mapping = map_headers(headers, aliases)
        if not mapping:
            raise MizanParseError("Tanınan sütun başlığı bulunamadı.")
        df = rows_to_dataframe(
            rows, mapping, required=required, numeric_cols=numeric_cols
        )
        return coerce(df, file_path)
    except (MizanParseError, MissingColumnError, FileNotFoundError):
        raise
    except Exception as exc:
        raise MizanParseError(f"Dosya okunurken hata: {exc}") from exc
