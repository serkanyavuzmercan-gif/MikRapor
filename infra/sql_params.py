"""
SQL'e gömülen parametreler için doğrulama / kaçış.

Mikro SqlVeriOkuV2 parametreli sorgu kabul etmez; tarih ve firma kodu f-string ile
SQL'e yazılır. Bu modül enjeksiyon riskini sınırlar:
  - tarih: yalnızca geçerli ISO `YYYY-MM-DD`
  - firma kodu: dar karakter kümesi
  - string literal: tek tırnak çiftlenerek kaçış
"""

from __future__ import annotations

import re
from datetime import date

# Mikro firma kodları tipik olarak kısa alfanümerik (örn. 01, 26, FIRM-A).
_FIRMA_KODU_RE = re.compile(r"^[A-Za-z0-9._\-/]{1,32}$")


def iso_tarih(value: str, *, alan: str = "tarih") -> str:
    """YYYY-MM-DD doğrular; geçerliyse normalize edilmiş string döner."""
    s = str(value or "").strip()
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        raise ValueError(f"Geçersiz {alan}: {s!r} (YYYY-MM-DD beklenir)")
    try:
        date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"Geçersiz {alan}: {s!r} (YYYY-MM-DD beklenir)") from exc
    return s


def firma_kodu_guvenli(value: str) -> str:
    """Firma kodunu doğrular; boşsa boş string, geçersizse ValueError."""
    s = str(value or "").strip()
    if not s:
        return ""
    if not _FIRMA_KODU_RE.fullmatch(s):
        raise ValueError(
            f"Geçersiz firma kodu: {s!r} "
            "(yalnızca harf, rakam, . _ - / ; en fazla 32 karakter)"
        )
    return s


def sql_string(value: str) -> str:
    """SQL string literal üretir (tek tırnak kaçışlı, tırnaklar dahil)."""
    return "'" + str(value).replace("'", "''") + "'"
