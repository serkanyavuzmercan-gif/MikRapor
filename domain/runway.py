"""
Nakit Runway motoru — "paran kaç ay yeter / hangi ay eksiye düşer".

Muhasebe kârından DEĞİL, fiili nakit hareketinden çalışır: mevcut nakit +
aylık ortalama net nakit hızı ile ileriye projeksiyon. Nakit ilk kez eksiye
düştüğü ayı ve yaklaşık günü verir. Saf fonksiyon (Mikro/DB/GUI yok) — test edilir.

4a sürümü run-rate tabanlıdır (aylık net nakit ortalaması sabit varsayılır). Sonraki
sürüm (4b) tahsilat vade takvimi + düzenli gider kırılımıyla gün-gün kesinleştirir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GUN_AY = 30.44  # ortalama ay uzunluğu (gün)


def _ay_ekle(yyyymm: str, k: int) -> str:
    """'2026-06' + k ay → 'YYYY-MM'."""
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
    except (ValueError, IndexError):
        return ""
    idx = y * 12 + (m - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


@dataclass
class RunwayAy:
    ay: str            # YYYY-MM
    net: float = 0.0   # o ay beklenen net nakit
    nakit: float = 0.0 # ay sonu kümülatif nakit


@dataclass
class Runway:
    baslangic_nakit: float = 0.0
    aylik_net_ort: float = 0.0
    ufuk_ay: int = 12
    aylar: list[RunwayAy] = field(default_factory=list)
    tukenme_ay: str | None = None   # nakitin ilk eksiye düştüğü ay (YYYY-MM) veya None
    tukenme_gun: int | None = None  # yaklaşık kaç gün sonra eksiye düşer
    en_dusuk_nakit: float = 0.0

    @property
    def eriyor(self) -> bool:
        """Aylık ortalama net nakit negatif → nakit trend olarak azalıyor."""
        return self.aylik_net_ort < -0.005

    @property
    def surdurulebilir(self) -> bool:
        """Ufuk boyunca nakit eksiye düşmüyor."""
        return self.tukenme_ay is None


def build_runway(
    *,
    baslangic_nakit: float,
    aylik_net_ort: float,
    baslangic_ay: str,
    ufuk_ay: int = 12,
) -> Runway:
    """Mevcut nakit + aylık ortalama net nakit hızından ileriye runway projeksiyonu."""
    r = Runway(
        baslangic_nakit=baslangic_nakit,
        aylik_net_ort=aylik_net_ort,
        ufuk_ay=max(1, ufuk_ay),
    )
    nakit = baslangic_nakit
    r.en_dusuk_nakit = nakit
    for n in range(1, r.ufuk_ay + 1):
        nakit += aylik_net_ort
        ay = _ay_ekle(baslangic_ay, n)
        r.aylar.append(RunwayAy(ay=ay, net=aylik_net_ort, nakit=nakit))
        if nakit < r.en_dusuk_nakit:
            r.en_dusuk_nakit = nakit
        if r.tukenme_ay is None and nakit < 0:
            r.tukenme_ay = ay

    # Yaklaşık tükenme günü (sürekli model): nakit / aylık erime hızı.
    if aylik_net_ort < -0.005:
        if baslangic_nakit <= 0:
            r.tukenme_gun = 0
        else:
            r.tukenme_gun = int(round(baslangic_nakit / (-aylik_net_ort) * GUN_AY))
    return r


def runway_nakit_akistan(na, *, baslangic_ay: str = "", ufuk_ay: int = 12) -> Runway:
    """NakitAkis modelinden runway kurar: kapanış nakiti + aylık net ortalaması."""
    aylik = getattr(na, "aylik", None) or []
    if aylik:
        aylik_net_ort = sum(a.net for a in aylik) / len(aylik)
    else:
        aylik_net_ort = na.net_akis  # tek dönem: dönem netini aylık kabul et
    if not baslangic_ay:
        baslangic_ay = (na.bit or "")[:7]
    return build_runway(
        baslangic_nakit=na.kapanis_nakit,
        aylik_net_ort=aylik_net_ort,
        baslangic_ay=baslangic_ay,
        ufuk_ay=ufuk_ay,
    )
