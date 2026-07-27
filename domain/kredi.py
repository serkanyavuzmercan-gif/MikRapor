"""
Banka kredisi taksit takvimi — Mikro KREDI_SOZLESMESI_TAKSIT_TANIMLARI'ndan.

Ödenmemiş taksitleri modelleyip (a) runway'e ay-ay gerçek kredi ödemesi olarak besler,
(b) Nakit Akış'ta "Yaklaşan Taksitler" özetini üretir. Saf fonksiyonlar (Mikro/DB/GUI yok).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from domain.ortak import to_float as _f


# Varsayılan senaryo: firma kart ekstresini tam kapatır. Tahmin ekranında kullanıcı değiştirebilir.
KART_BORCU_VARSAYILAN_ODEME_YUZDE = 100.0


def _ay_ekle(yyyymm: str, k: int) -> str:
    try:
        yil, ay = int(yyyymm[:4]), int(yyyymm[5:7])
    except (ValueError, IndexError):
        return ""
    idx = yil * 12 + (ay - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


@dataclass
class KrediTaksit:
    ay: str            # YYYY-MM (vade ayı)
    vade: str          # YYYY-MM-DD
    tutar: float       # toplam taksit (anapara + faiz + vergiler) — nakit çıkışı
    anapara: float = 0.0
    faiz: float = 0.0
    banka: str = ""       # banka hesap kodu (krsoz_sozbankakodu)
    banka_ad: str = ""    # BANKALAR.ban_ismi


@dataclass
class KrediOdeme:
    tarih: str
    hesap: str
    hesap_ad: str
    tutar: float


@dataclass
class KrediKartiBorcu:
    hesap: str
    hesap_ad: str
    borc: float


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
            banka_ad=str(r.get("banka_ad", r.get("BANKA_AD")) or "").strip(),
        ))
    out.sort(key=lambda t: t.vade)
    return out


def kredi_odemelerini_derle(rows: list[dict] | None) -> list[KrediOdeme]:
    """Muhasebe kaynaklı dönem kredi ödeme detaylarını temizler ve tarihe göre sıralar."""
    out: list[KrediOdeme] = []
    for r in (rows or []):
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if tutar < 0.005:
            continue
        out.append(KrediOdeme(
            tarih=str(r.get("tarih", r.get("TARIH")) or "")[:10],
            hesap=str(r.get("hesap", r.get("HESAP")) or "").strip(),
            hesap_ad=str(r.get("hesap_ad", r.get("HESAP_AD")) or "").strip(),
            tutar=tutar,
        ))
    out.sort(key=lambda o: (o.tarih, o.hesap))
    return out


def kredi_karti_borclarini_derle(rows: list[dict] | None) -> list[KrediKartiBorcu]:
    """Açık kredi kartı borçlarını pozitif TL tutarıyla temizler."""
    out: list[KrediKartiBorcu] = []
    for r in (rows or []):
        borc = _f(r.get("borc", r.get("BORC")))
        if borc < 0.005:
            continue
        out.append(KrediKartiBorcu(
            hesap=str(r.get("hesap", r.get("HESAP")) or "").strip(),
            hesap_ad=str(r.get("hesap_ad", r.get("HESAP_AD")) or "").strip(),
            borc=borc,
        ))
    out.sort(key=lambda k: (-k.borc, k.hesap))
    return out


def kredi_karti_odeme_takvimi(
    borclar: list[KrediKartiBorcu] | None,
    *,
    baslangic_ay: str,
    odeme_yuzde: float = KART_BORCU_VARSAYILAN_ODEME_YUZDE,
    ufuk_ay: int = 12,
) -> dict[str, float]:
    """Mevcut açık kart borcunu, seçilebilir aylık ödeme oranıyla projeksiyona dağıtır.

    Bu yalnızca projeksiyon başlangıcındaki AÇIK borçtur. Gelecekteki kart harcamaları ayrıca
    eklenmez; tahmin modelinin ciro/gider varsayımları bu yeni harcamaların etkisini zaten
    aynı ayın nakit sonucuna dahil eder. Oran, ekstre/veri olmadığı için bir senaryodur.
    """
    kalan = sum(max(0.0, k.borc) for k in (borclar or []))
    oran = min(100.0, max(0.0, float(odeme_yuzde))) / 100.0
    takvim: dict[str, float] = {}
    for n in range(1, max(0, int(ufuk_ay)) + 1):
        if kalan < 0.005 or oran <= 0.0:
            break
        ay = _ay_ekle(baslangic_ay, n)
        odeme = min(kalan, kalan * oran)
        takvim[ay] = odeme
        kalan -= odeme
    return takvim


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
