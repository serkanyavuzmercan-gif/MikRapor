"""
Analiz ayı ve dönem filtreleri.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime

import pandas as pd

ANALIZ_AY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def parse_analiz_ayi(analiz_ayi: str) -> tuple[int, int]:
    """'2026-03' -> (2026, 3)."""
    match = ANALIZ_AY_PATTERN.match(str(analiz_ayi).strip())
    if not match:
        raise ValueError(f"Geçersiz analiz ayı: {analiz_ayi!r} (beklenen: YYYY-MM)")
    year, month = int(match.group(1)), int(match.group(2))
    if month < 1 or month > 12:
        raise ValueError(f"Geçersiz ay: {month}")
    return year, month


def analiz_ayi_araligi(analiz_ayi: str) -> tuple[date, date]:
    """Analiz ayının ilk ve son gününü döndürür."""
    year, month = parse_analiz_ayi(analiz_ayi)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def analiz_ayi_label(analiz_ayi: str) -> str:
    """'2026-03' -> 'Mart 2026'."""
    year, month = parse_analiz_ayi(analiz_ayi)
    names = (
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    )
    return f"{names[month - 1]} {year}"


def filter_df_by_analiz_ayi(
    df: pd.DataFrame | None,
    tarih_kolonu: str,
    analiz_ayi: str,
) -> pd.DataFrame:
    """DataFrame'i seçilen analiz ayına göre filtreler."""
    if df is None or df.empty:
        return pd.DataFrame()
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    work = df.copy()
    if tarih_kolonu not in work.columns:
        return work
    work[tarih_kolonu] = pd.to_datetime(work[tarih_kolonu], errors="coerce", dayfirst=True)
    mask = (work[tarih_kolonu].dt.date >= bas) & (work[tarih_kolonu].dt.date <= bit)
    return work[mask].copy()


def recent_analiz_aylari(count: int = 24) -> list[str]:
    """Son N ay için YYYY-MM listesi (en yeniden eskiye)."""
    today = date.today()
    result: list[str] = []
    year, month = today.year, today.month
    for _ in range(count):
        result.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return result


def format_analiz_donem(analiz_ayi: str) -> str:
    """Rapor başlığı için dönem metni."""
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    return f"{bas.strftime('%d.%m.%Y')} – {bit.strftime('%d.%m.%Y')}"


def previous_analiz_ayi(analiz_ayi: str) -> str:
    """Bir önceki ayı YYYY-MM olarak döndürür."""
    year, month = parse_analiz_ayi(analiz_ayi)
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    return f"{year:04d}-{month:02d}"
