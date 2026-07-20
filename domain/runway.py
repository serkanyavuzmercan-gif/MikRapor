"""
Nakit Runway motoru — "paran kaç ay yeter / hangi ay eksiye düşer".

Muhasebe kârından DEĞİL, fiili nakit hareketinden çalışır: mevcut nakit +
aylık ortalama net nakit hızı ile ileriye projeksiyon. Nakit ilk kez eksiye
düştüğü ayı ve yaklaşık günü verir. Saf fonksiyon (Mikro/DB/GUI yok) — test edilir.

4a sürümü run-rate tabanlıdır (aylık net nakit ortalaması sabit varsayılır). Sonraki
sürüm (4b) tahsilat vade takvimi + düzenli gider kırılımıyla gün-gün kesinleştirir.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from domain.tahsilat_alacak import VADE_KOVALAR

GUN_AY = 30.44  # ortalama ay uzunluğu (gün)

# Tahsilat vade kovası (index) → projeksiyonda hangi ay (1-indexli).
# Gecikmiş + Bu hafta + Bu ay → 1. ay; Gelecek ay → 2.; Sonrası → 3.
_KOVA_AY = {
    VADE_KOVALAR[0]: 1,  # Gecikmiş
    VADE_KOVALAR[1]: 1,  # Bu hafta (0–7g)
    VADE_KOVALAR[2]: 1,  # Bu ay (8–30g)
    VADE_KOVALAR[3]: 2,  # Gelecek ay (31–60g)
    VADE_KOVALAR[4]: 3,  # Sonrası (60+g)
}


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


# --- 4b: Takvim tabanlı (vade) runway -------------------------------------

@dataclass
class RunwayTakvimAy:
    ay: str            # YYYY-MM
    giren: float = 0.0 # o ay beklenen tahsilat (açık alacak vadesi)
    cikan: float = 0.0 # o ay beklenen ödeme (satıcı vadesi + düzenli gider + kredi)
    nakit: float = 0.0 # ay sonu kümülatif nakit

    @property
    def net(self) -> float:
        return self.giren - self.cikan


@dataclass
class RunwayTakvim:
    baslangic_nakit: float = 0.0
    aylik_gider: float = 0.0      # düzenli aylık gider (maaş+SGK+vergi+genel)
    aylik_kredi: float = 0.0      # düzenli aylık kredi ödemesi
    ufuk_ay: int = 6
    aylar: list[RunwayTakvimAy] = field(default_factory=list)
    tukenme_ay: str | None = None
    en_dusuk_nakit: float = 0.0
    en_dusuk_ay: str = ""
    gider_eksik: bool = False  # aylık düzenli gider ~0 → maaş/gider kategorize edilememiş

    @property
    def surdurulebilir(self) -> bool:
        return self.tukenme_ay is None


def build_runway_takvim(
    *,
    baslangic_nakit: float,
    baslangic_ay: str,
    alacak_vade: dict | None = None,
    borc_vade: dict | None = None,
    aylik_gider: float = 0.0,
    aylik_kredi: float = 0.0,
    ufuk_ay: int = 6,
) -> RunwayTakvim:
    """
    Açık alacak/borç vade kovaları aylara dağıtılıp düzenli gider + kredi ile
    ay-ay nakit projeksiyonu. KONSERVATİF: açık kalemler bittikten sonra yeni
    satış varsaymaz — yalnız düzenli giderler devam eder (en kötü hal / taban).
    """
    r = RunwayTakvim(
        baslangic_nakit=baslangic_nakit, aylik_gider=aylik_gider,
        aylik_kredi=aylik_kredi, ufuk_ay=max(1, ufuk_ay),
        gider_eksik=(aylik_gider + aylik_kredi) < 1.0,
    )
    ay_giren: dict[int, float] = defaultdict(float)
    ay_cikan: dict[int, float] = defaultdict(float)
    for kova, tutar in (alacak_vade or {}).items():
        ay_giren[_KOVA_AY.get(kova, 3)] += tutar
    for kova, tutar in (borc_vade or {}).items():
        ay_cikan[_KOVA_AY.get(kova, 3)] += tutar

    nakit = baslangic_nakit
    r.en_dusuk_nakit = nakit
    r.en_dusuk_ay = baslangic_ay
    for n in range(1, r.ufuk_ay + 1):
        giren = ay_giren.get(n, 0.0)
        cikan = ay_cikan.get(n, 0.0) + aylik_gider + aylik_kredi
        nakit += giren - cikan
        ay = _ay_ekle(baslangic_ay, n)
        r.aylar.append(RunwayTakvimAy(ay=ay, giren=giren, cikan=cikan, nakit=nakit))
        if nakit < r.en_dusuk_nakit:
            r.en_dusuk_nakit, r.en_dusuk_ay = nakit, ay
        if r.tukenme_ay is None and nakit < 0:
            r.tukenme_ay = ay
    return r


def runway_takvim_kur(
    *, na, ta, baslangic_ay: str = "", ufuk_ay: int = 6,
    baslangic_nakit: float | None = None,
) -> RunwayTakvim:
    """
    NakitAkis (düzenli gider run-rate) + TahsilatAlacak (vade takvimi) birleşiminden
    takvim runway'i kurar. Düzenli gider = maaş+SGK+vergi+genel gider aylık ortalaması;
    kredi = kredi ödemesi aylık ortalaması.

    baslangic_nakit verilirse (GL/mizan nakiti) onu kullanır — cari-hareket nakiti döviz
    kuru yüzünden onlarca kat şişebildiği için GÜVENİLİR kaynak GL'dir.
    """
    ay_sayisi = max(1, len(getattr(na, "aylik", None) or [1]))
    ck = getattr(na, "cikis_kategori", {}) or {}
    duzenli = (
        ck.get("Personel / Maaş", 0.0) + ck.get("SGK", 0.0)
        + ck.get("Vergi", 0.0) + ck.get("Genel giderler", 0.0)
    ) / ay_sayisi
    kredi = getattr(na, "kredi_odeme", 0.0) / ay_sayisi
    if not baslangic_ay:
        baslangic_ay = (getattr(na, "bit", "") or "")[:7]
    nakit = baslangic_nakit if baslangic_nakit is not None else na.kapanis_nakit
    return build_runway_takvim(
        baslangic_nakit=nakit, baslangic_ay=baslangic_ay,
        alacak_vade=getattr(ta, "alacak_vade", {}), borc_vade=getattr(ta, "borc_vade", {}),
        aylik_gider=duzenli, aylik_kredi=kredi, ufuk_ay=ufuk_ay,
    )
