"""
Banka kredisi taksit takvimi — Mikro KREDI_SOZLESMESI_TAKSIT_TANIMLARI'ndan.

Ödenmemiş taksitleri modelleyip (a) runway'e ay-ay gerçek kredi ödemesi olarak besler,
(b) Nakit Akış'ta "Yaklaşan Taksitler" özetini üretir. Saf fonksiyonlar (Mikro/DB/GUI yok).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from domain.ortak import to_float as _f


@dataclass
class KrediTaksit:
    ay: str            # YYYY-MM (vade ayı)
    vade: str          # YYYY-MM-DD
    tutar: float       # toplam taksit (anapara + faiz + vergiler) — nakit çıkışı
    anapara: float = 0.0
    faiz: float = 0.0
    banka: str = ""


@dataclass
class KrediOzet:
    taksitler: list[KrediTaksit] = field(default_factory=list)  # vadeye göre sıralı
    toplam: float = 0.0
    toplam_anapara: float = 0.0
    toplam_faiz: float = 0.0
    gecikmis_tutar: float = 0.0   # vadesi geçmiş ama ödenmemiş
    gecikmis_adet: int = 0

    @property
    def adet(self) -> int:
        return len(self.taksitler)


def taksitleri_derle(rows: list[dict] | None) -> list[KrediTaksit]:
    """fetch_kredi_taksitleri ham satırlarını KrediTaksit listesine çevirir (tutarı olanlar)."""
    out: list[KrediTaksit] = []
    for r in (rows or []):
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if tutar < 0.005:
            continue
        out.append(KrediTaksit(
            ay=str(r.get("ay", r.get("AY")) or "")[:7],
            vade=str(r.get("vade", r.get("VADE")) or "")[:10],
            tutar=tutar,
            anapara=_f(r.get("anapara", r.get("ANAPARA"))),
            faiz=_f(r.get("faiz", r.get("FAIZ"))),
            banka=str(r.get("banka", r.get("BANKA")) or "").strip(),
        ))
    out.sort(key=lambda t: t.vade)
    return out


def kredi_takvimi_ay(taksitler: list[KrediTaksit], *, ilk_ay: str) -> dict[str, float]:
    """
    Taksitleri vade ayına göre toplar → {YYYY-MM: toplam}. Vadesi ilk_ay'dan önce olan
    (gecikmiş, hâlâ ödenmemiş) taksitler ilk_ay'a yığılır — yakında ödenecek borçtur.
    """
    d: dict[str, float] = defaultdict(float)
    for t in taksitler:
        ay = t.ay if t.ay and t.ay >= ilk_ay else ilk_ay
        d[ay] += t.tutar
    return dict(d)


def kredi_ozet(taksitler: list[KrediTaksit], *, bugun_ay: str = "", en_fazla: int = 8) -> KrediOzet:
    """Yaklaşan taksitlerden özet: ilk `en_fazla` taksit + toplamlar + gecikmiş."""
    oz = KrediOzet(taksitler=taksitler[:en_fazla])
    for t in taksitler:
        oz.toplam += t.tutar
        oz.toplam_anapara += t.anapara
        oz.toplam_faiz += t.faiz
        if bugun_ay and t.ay and t.ay < bugun_ay:
            oz.gecikmis_tutar += t.tutar
            oz.gecikmis_adet += 1
    return oz
