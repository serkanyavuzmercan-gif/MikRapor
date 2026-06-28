"""
Tahsilat & Alacak motoru — Mikro cari hareketlerinden, resmi GL'ye dokunmadan.

Tamamen CARI_HESAP_HAREKETLERI ham verisine dayanır (Nakit & Kârlılık ile aynı kaynak ailesi):
müşteri alacakları ve satıcı borçları, fiili vade tarihine göre yaşlandırılır; dönem tahsilat/
ödeme performansı ve ileriye dönük net vade takvimi (ne girecek − ne çıkacak) çıkarılır.

YAŞLANDIRMA (FIFO açık kalem): Her cari için borçlandırıcı hareketler (müşteride satış,
satıcıda alış) vadeye göre eskiden yeniye sıralanır; ödemeler en eski borçtan başlayarak düşülür
(FIFO). Kalan açık parçalar kendi vadeleriyle kovalanır. Ödeme borçtan fazlaysa kalan = avans.

İŞARET KURALI: tutarlar pozitif büyüklüktür; yön cha_tip ile gelir (0=borç hareketi, 1=alacak
hareketi). Müşteri (120/121): borç→satış(+alacak), alacak→tahsilat(−). Satıcı (320/321/329):
alacak→alış(+borç), borç→ödeme(−). Sınıf cari_muh_kod önekiyle, yoksa bağlantı/hareket tipiyle.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from gercek_durum import _muh_sinifi, _f, _i

# Yaşlandırma kovaları — vade gününe göre gecikme (asof − vade).
AGING_KOVALAR = ("Vadesi gelmemiş", "1–30 gün", "31–60 gün", "61–90 gün", "90+ gün")
# İleriye dönük vade takvimi kovaları — vade tarihine göre (vade − asof).
VADE_KOVALAR = ("Gecikmiş", "Bu hafta (0–7g)", "Bu ay (8–30g)", "Gelecek ay (31–60g)", "Sonrası (60+g)")


def _gun_yaslandirma_kovasi(gecikme_gun: int) -> str:
    """asof − vade (gün) → yaşlandırma kovası."""
    if gecikme_gun <= 0:
        return AGING_KOVALAR[0]
    if gecikme_gun <= 30:
        return AGING_KOVALAR[1]
    if gecikme_gun <= 60:
        return AGING_KOVALAR[2]
    if gecikme_gun <= 90:
        return AGING_KOVALAR[3]
    return AGING_KOVALAR[4]


def _gun_vade_kovasi(kalan_gun: int) -> str:
    """vade − asof (gün) → ileriye dönük vade kovası."""
    if kalan_gun < 0:
        return VADE_KOVALAR[0]
    if kalan_gun <= 7:
        return VADE_KOVALAR[1]
    if kalan_gun <= 30:
        return VADE_KOVALAR[2]
    if kalan_gun <= 60:
        return VADE_KOVALAR[3]
    return VADE_KOVALAR[4]


def _tarih(v: object) -> date | None:
    s = str(v or "").strip()
    if not s:
        return None
    s = s.replace("T", " ").split(" ")[0]
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return None
    # Mikro boş tarihi 1899-12-30 sentinel'i olarak tutabilir → yok say.
    return d if d.year >= 1900 else None


def tl0(v: float) -> str:
    """Yuvarlanmış TL gösterimi (Türkçe binlik) — view dışı CLI/test için."""
    return f"{v:,.0f}".replace(",", ".")


@dataclass
class CariOzet:
    """Bir carinin açık net bakiyesi ve gecikmiş kısmı (top listeler için)."""
    kod: str
    unvan: str
    sinif: str          # "customer" | "supplier"
    net: float          # müşteride alacak(+), satıcıda borç(+)
    gecikmis: float     # vadesi geçmiş açık kısım


@dataclass
class TahsilatAlacak:
    bas: str = ""
    bit: str = ""
    vade_kaynagi: str = "vade"   # "vade" | "tarih" (vade kolonu yoksa cha_tarihi'ne düşülür)

    # Bakiye toplamları (asof = bit)
    alacak_toplam: float = 0.0
    borc_toplam: float = 0.0
    alacak_gecikmis: float = 0.0
    borc_gecikmis: float = 0.0
    musteri_avans: float = 0.0
    satici_avans: float = 0.0
    cari_sayisi: int = 0

    # Yaşlandırma (kova → tutar)
    alacak_aging: dict = field(default_factory=dict)
    borc_aging: dict = field(default_factory=dict)

    # İleriye dönük vade takvimi (kova → tutar)
    alacak_vade: dict = field(default_factory=dict)
    borc_vade: dict = field(default_factory=dict)

    # En yüksek bakiyeler
    top_alacak: list = field(default_factory=list)
    top_borc: list = field(default_factory=list)

    # Dönem performansı (bas..bit)
    donem_gun: int = 0
    donem_tahsilat: float = 0.0
    donem_satis: float = 0.0
    donem_odeme: float = 0.0
    donem_alis: float = 0.0

    @property
    def net_pozisyon(self) -> float:
        """Alacak − borç (pozitif = net alacaklıyız)."""
        return self.alacak_toplam - self.borc_toplam

    @property
    def tahsilat_orani(self) -> float | None:
        """Dönem tahsilat / dönem kredili satış (%)."""
        if self.donem_satis <= 0.005:
            return None
        return self.donem_tahsilat / self.donem_satis * 100

    @property
    def odeme_orani(self) -> float | None:
        if self.donem_alis <= 0.005:
            return None
        return self.donem_odeme / self.donem_alis * 100

    @property
    def dso(self) -> float | None:
        """Ortalama tahsilat süresi (gün) ≈ alacak ÷ (günlük kredili satış)."""
        if self.donem_satis <= 0.005 or self.donem_gun <= 0:
            return None
        return self.alacak_toplam / (self.donem_satis / self.donem_gun)

    @property
    def dpo(self) -> float | None:
        """Ortalama ödeme süresi (gün) ≈ borç ÷ (günlük alış)."""
        if self.donem_alis <= 0.005 or self.donem_gun <= 0:
            return None
        return self.borc_toplam / (self.donem_alis / self.donem_gun)

    def net_vade(self) -> dict:
        """Kova → beklenen net nakit (alacak girişi − borç çıkışı)."""
        return {
            k: self.alacak_vade.get(k, 0.0) - self.borc_vade.get(k, 0.0)
            for k in VADE_KOVALAR
        }


def _sinif_belirle(muh_kod: str, hareket_tipi: int, baglanti_tipi: int, kod: str = "") -> str:
    """
    Müşteri/satıcı sınıfı: önce cari_muh_kod (120/320), yoksa hareket/bağlantı tipi,
    son çare cari kod öneki. (Bu kurulumda muh_kod genelde dolu — kanıtlı yol.)
    """
    s = _muh_sinifi(muh_kod)
    if s:
        return s
    if hareket_tipi == 1 or baglanti_tipi == 0:
        return "customer"
    if hareket_tipi == 2 or baglanti_tipi == 1:
        return "supplier"
    k = str(kod or "").strip()
    if k.startswith("120") or k.startswith("121"):
        return "customer"
    if k.startswith("320") or k.startswith("321") or k.startswith("329"):
        return "supplier"
    return ""


def _vade_hesapla(cha_vade: date | None, evrak: date | None, vade_gun: int | None) -> date | None:
    """cha_vade doluysa o; yoksa evrak tarihi + carinin ödeme planı günü."""
    if cha_vade is not None:
        return cha_vade
    if evrak is None:
        return None
    return evrak + timedelta(days=vade_gun or 0)


def _fifo_acik(charges: list[tuple[date | None, float]], odeme: float,
               asof: date) -> tuple[list[tuple[int, float]], float]:
    """
    Ödemeyi en eski borçtan başlayarak düşer (FIFO). Kalan açık parçaları
    (gecikme_gun, tutar) listesi + artan ödemeyi (avans) döndürür.
    """
    acik: list[tuple[int, float]] = []
    kalan_odeme = odeme
    # Vadesi olmayan parçalar en eski kabul edilsin (önce kapansın).
    sirali = sorted(charges, key=lambda c: c[0] or date.min)
    for vade, tutar in sirali:
        if kalan_odeme >= tutar - 0.005:
            kalan_odeme -= tutar
            continue
        acik_tutar = tutar - max(kalan_odeme, 0.0)
        kalan_odeme = 0.0
        v = vade or asof
        acik.append(((asof - v).days, acik_tutar))
    return acik, max(kalan_odeme, 0.0)


def build_tahsilat_alacak(
    acik_rows: list[dict] | None = None,
    *,
    vade_gun_map: dict | None = None,
    bas: str = "",
    bit: str = "",
    top_n: int = 8,
) -> TahsilatAlacak:
    """fetch_acik_kalemler satırlarından Tahsilat & Alacak modelini kurar."""
    vade_gun_map = vade_gun_map or {}
    ta = TahsilatAlacak(bas=bas, bit=bit)
    asof = _tarih(bit) or date.today()
    _cha_vade_var = False
    _plan_var = bool(vade_gun_map)
    bas_d = _tarih(bas)
    ta.donem_gun = ((asof - bas_d).days + 1) if (bas_d and asof >= bas_d) else 0

    ta.alacak_aging = {k: 0.0 for k in AGING_KOVALAR}
    ta.borc_aging = {k: 0.0 for k in AGING_KOVALAR}
    ta.alacak_vade = {k: 0.0 for k in VADE_KOVALAR}
    ta.borc_vade = {k: 0.0 for k in VADE_KOVALAR}

    # kod → toplanan satırlar
    gruplar: dict[str, list[dict]] = defaultdict(list)
    for r in (acik_rows or []):
        gruplar[str(r.get("kod", r.get("KOD")) or "")].append(r)

    musteri: list[CariOzet] = []
    satici: list[CariOzet] = []

    for kod, rows in gruplar.items():
        if not kod:
            continue
        unvan = ""
        muh = ""
        ht = bt = -1
        for r in rows:
            unvan = unvan or str(r.get("unvan", r.get("UNVAN")) or "")
            muh = muh or str(r.get("muh_kod", r.get("MUH_KOD")) or "")
            if ht < 0:
                ht = _i(r.get("hareket_tipi", r.get("HAREKET_TIPI")))
            if bt < 0:
                bt = _i(r.get("baglanti_tipi", r.get("BAGLANTI_TIPI")))
        sinif = _sinif_belirle(muh, ht, bt, kod)
        if not sinif:
            continue
        vade_gun = vade_gun_map.get(kod)

        # Müşteride borç(tip0)=satış/charge, alacak(tip1)=tahsilat/ödeme.
        # Satıcıda alacak(tip1)=alış/charge, borç(tip0)=ödeme.
        charge_tip = 0 if sinif == "customer" else 1
        charges: list[tuple[date | None, float]] = []
        odeme = 0.0
        donem_charge = donem_odeme = 0.0
        for r in rows:
            tip = _i(r.get("tip", r.get("TIP")))
            tutar = _f(r.get("tutar", r.get("TUTAR")))
            tutar_donem = _f(r.get("tutar_donem", r.get("TUTAR_DONEM")))
            cha_vade = _tarih(r.get("cha_vade", r.get("CHA_VADE")))
            evrak = _tarih(r.get("evrak_tarihi", r.get("EVRAK_TARIHI")))
            if cha_vade is not None:
                _cha_vade_var = True
            vade = _vade_hesapla(cha_vade, evrak, vade_gun)
            if tip == charge_tip:
                charges.append((vade, tutar))
                donem_charge += tutar_donem
            else:
                odeme += tutar
                donem_odeme += tutar_donem

        if sinif == "customer":
            ta.donem_satis += donem_charge
            ta.donem_tahsilat += donem_odeme
        else:
            ta.donem_alis += donem_charge
            ta.donem_odeme += donem_odeme

        acik, avans = _fifo_acik(charges, odeme, asof)
        net = sum(t for _, t in acik)
        if avans > 0.005:
            if sinif == "customer":
                ta.musteri_avans += avans
            else:
                ta.satici_avans += avans
        if net <= 0.005:
            continue

        ta.cari_sayisi += 1
        gecikmis = 0.0
        aging = ta.alacak_aging if sinif == "customer" else ta.borc_aging
        vade_kov = ta.alacak_vade if sinif == "customer" else ta.borc_vade
        for gecikme_gun, tutar in acik:
            aging[_gun_yaslandirma_kovasi(gecikme_gun)] += tutar
            vade_kov[_gun_vade_kovasi(-gecikme_gun)] += tutar
            if gecikme_gun > 0:
                gecikmis += tutar

        ozet = CariOzet(kod=kod, unvan=unvan or kod, sinif=sinif, net=net, gecikmis=gecikmis)
        if sinif == "customer":
            ta.alacak_toplam += net
            ta.alacak_gecikmis += gecikmis
            musteri.append(ozet)
        else:
            ta.borc_toplam += net
            ta.borc_gecikmis += gecikmis
            satici.append(ozet)

    ta.vade_kaynagi = "vade" if _cha_vade_var else ("plan" if _plan_var else "tarih")
    ta.top_alacak = sorted(musteri, key=lambda c: c.net, reverse=True)[:top_n]
    ta.top_borc = sorted(satici, key=lambda c: c.net, reverse=True)[:top_n]
    return ta


def _gun(v: float | None) -> str:
    return "—" if v is None else f"{v:.0f} gün"


def tahsilat_alacak_csv(ta: TahsilatAlacak) -> str:
    """Tahsilat & Alacak özetini CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    def s(v: float | None) -> str:
        return "" if v is None else f"{v:.2f}".replace(".", ",")

    out = ["Bölüm;Kalem;Tutar (TL)"]
    out.append(f"DÖNEM;{ta.bas} - {ta.bit} ({ta.donem_gun} gün);")
    out.append(f"BAKİYE;Toplam Alacak;{s(ta.alacak_toplam)}")
    out.append(f"BAKİYE;  • gecikmiş;{s(ta.alacak_gecikmis)}")
    out.append(f"BAKİYE;Toplam Borç;{s(ta.borc_toplam)}")
    out.append(f"BAKİYE;  • gecikmiş;{s(ta.borc_gecikmis)}")
    out.append(f"BAKİYE;Net Pozisyon (alacak−borç);{s(ta.net_pozisyon)}")
    if ta.musteri_avans > 0.005:
        out.append(f"BAKİYE;Müşteri avansı;{s(ta.musteri_avans)}")
    if ta.satici_avans > 0.005:
        out.append(f"BAKİYE;Satıcı avansı;{s(ta.satici_avans)}")
    for k in AGING_KOVALAR:
        out.append(f"ALACAK YAŞLANDIRMA;{k};{s(ta.alacak_aging.get(k, 0.0))}")
    for k in AGING_KOVALAR:
        out.append(f"BORÇ YAŞLANDIRMA;{k};{s(ta.borc_aging.get(k, 0.0))}")
    nv = ta.net_vade()
    for k in VADE_KOVALAR:
        out.append(f"VADE TAKVİMİ;{k} (alacak);{s(ta.alacak_vade.get(k, 0.0))}")
        out.append(f"VADE TAKVİMİ;{k} (borç);{s(ta.borc_vade.get(k, 0.0))}")
        out.append(f"VADE TAKVİMİ;{k} (net);{s(nv.get(k, 0.0))}")
    out.append(f"PERFORMANS;Dönem Tahsilatı;{s(ta.donem_tahsilat)}")
    out.append(f"PERFORMANS;Dönem Kredili Satış;{s(ta.donem_satis)}")
    out.append(f"PERFORMANS;Dönem Ödeme;{s(ta.donem_odeme)}")
    out.append(f"PERFORMANS;Dönem Alış;{s(ta.donem_alis)}")
    if ta.tahsilat_orani is not None:
        out.append(f"PERFORMANS;Tahsilat Oranı;%{ta.tahsilat_orani:.1f}".replace(".", ","))
    out.append(f"PERFORMANS;Ort. Tahsilat Süresi (DSO);{_gun(ta.dso)}")
    out.append(f"PERFORMANS;Ort. Ödeme Süresi (DPO);{_gun(ta.dpo)}")
    for c in ta.top_alacak:
        out.append(f"EN ÇOK ALACAK;{c.unvan};{s(c.net)}")
    for c in ta.top_borc:
        out.append(f"EN ÇOK BORÇ;{c.unvan};{s(c.net)}")
    return "\r\n".join(out)
