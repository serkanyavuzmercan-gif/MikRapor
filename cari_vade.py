"""
Cari ödeme vadesi — vade günü hesabı (ss/lib/cari-vade.ts Python portu).

Mikro bu kurulumda cha_vade'yi BOŞ bırakır; vade = evrak tarihi + carinin ödeme planı günü.
Plan günü: cari_odemeplan_no (< 0 → doğrudan gün) / ODEME_PLANLARI.odp_ortgun / plan adından
("30 GÜN" → 30) / bilinen Hidroteknik plan no tablosundan türetilir.
"""

from __future__ import annotations

import re

# Hidroteknik ödeme planı no → gün (cari-vade.ts ODEME_PLANI_ETIKET ile aynı).
ODEME_PLANI_GUN = {0: 0, 1: 0, 2: 30, 3: 60, 5: 45, 6: 75, 7: 90, 8: 100, 9: 120, 10: 7}

_GUN_RE = re.compile(r"(\d+)\s*G[ÜU]N")
_PESIN_RE = re.compile(r"PE[ŞS][İI]N")


def gun_from_plan_adi(plan_adi: str | None) -> int | None:
    """Plan adından gün çıkarır: "30 GÜN" → 30, "PEŞİN" → 0, eşleşmezse None."""
    if not plan_adi:
        return None
    s = str(plan_adi).upper()  # Türkçe İ/Ş için upper daha güvenli
    m = _GUN_RE.search(s)
    if m:
        return int(m.group(1))
    if _PESIN_RE.search(s):
        return 0
    return None


def hesapla_vade_gun(plan_no: int | None, plan_adi: str | None, odp_ortgun: int | None) -> int | None:
    """
    Vade gününü Mikro gerçeklerine göre hesaplar:
    - cari_odemeplan_no < 0  → doğrudan gün (örn. -60 = 60 gün)
    - cari_odemeplan_no = 0  → Peşin (0)
    - odp_ortgun > 0         → o değer
    - plan adı ("30 GÜN")    → çıkarılan gün
    - bilinen plan no tablosu → türetilen gün
    """
    if plan_no is not None and plan_no < 0:
        return abs(plan_no)
    if plan_no == 0:
        return 0
    if odp_ortgun is not None and odp_ortgun > 0:
        return odp_ortgun
    g = gun_from_plan_adi(plan_adi)
    if g is not None:
        return g
    if plan_no is not None and plan_no in ODEME_PLANI_GUN:
        return ODEME_PLANI_GUN[plan_no]
    return None
