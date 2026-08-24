"""
Vade etkisi — karar destek amaçlı saf hesaplama motoru.

TEK SORUYU CEVAPLAR: vadeli satmak neye mal oluyor, vadeli almak ne kazandırıyor?
Açık alacak/borçların vadelerine göre bugünkü ekonomik değerini hesaplar; nominal
muhasebe tutarlarını değiştirmez. Kullanılan oran senaryo varsayımıdır, resmî
muhasebe/vergisel değer değildir.

Kredi kartı finansman senaryosu BURADAN ÇIKARILDI (Tahmin & Projeksiyon'a taşındı):
sekmedeki dört değişkenin üçü yalnız en alttaki kart tablosunu besliyordu, panel bunu
söylemiyordu ve aynı kart borcu iki sekmede birden görünüyordu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.ortak import csv_metin, csv_sayi
from domain.tahsilat_alacak import TahsilatAlacak


@dataclass
class ReelDegerVarsayim:
    # TEK DEĞİŞKEN. Kredi kartı senaryosu Tahmin & Projeksiyon'a taşındı: bu sekmedeki
    # dört değişkenin ÜÇÜ yalnız en alttaki kart tablosunu besliyordu ve panel bunu
    # hiçbir yerde söylemiyordu. Sekme artık tek soruyu cevaplıyor: vadeli satmak neye
    # mal oluyor, vadeli almak ne kazandırıyor.
    yillik_iskonto_yuzde: float = 45.0


@dataclass
class DegerOzet:
    nominal: float = 0.0
    bugunku_deger: float = 0.0
    vade_etkisi: float = 0.0
    agirlikli_gun: float = 0.0


@dataclass
class CariErime:
    """Vade maliyetini/avantajını en çok büyüten cari — sıra BAKİYEYE değil erimeye göre."""
    kod: str
    unvan: str
    nominal: float
    agirlikli_gun: float
    vade_etkisi: float


# Başabaş vade farkı merdiveninde gösterilen vadeler (gün).
BASABAS_GUNLER: tuple[int, ...] = (30, 60, 90, 120, 180)


@dataclass
class ReelDegerAnalizi:
    varsayim: ReelDegerVarsayim = field(default_factory=ReelDegerVarsayim)
    alacak: DegerOzet = field(default_factory=DegerOzet)
    borc: DegerOzet = field(default_factory=DegerOzet)
    # Başabaş fark artık «vadeye kalan» değil ÖLÇÜLMÜŞ TAHSİL SÜRESİNE (DSO) çapalanır.
    # Kalan gün, tahsilat iyileştikçe düşer (FIFO en eski faturayı kapatır, açık kalanlar
    # en yeni faturalardır) — 90 gün vadeyle çalışan firmada %70 tahsilatta 20 güne
    # iniyordu ve başabaş tavsiyesini 5,5 kat eksik veriyordu.
    dso: float | None = None
    donem_gun: int = 0
    # Vadesi geçmiş tutar «bugün tahsil edilir» sayılıyor; erime bu yüzden ALT SINIRDIR.
    gecikmis_alacak: float = 0.0
    top_alacak_erime: list[CariErime] = field(default_factory=list)
    top_borc_erime: list[CariErime] = field(default_factory=list)

    @property
    def nominal_net_pozisyon(self) -> float:
        return self.alacak.nominal - self.borc.nominal

    @property
    def reel_net_pozisyon(self) -> float:
        return self.alacak.bugunku_deger - self.borc.bugunku_deger

    @property
    def net_vade_etkisi(self) -> float:
        """Vade nedeniyle net ekonomik pozisyondaki değişim (reel − nominal)."""
        return self.reel_net_pozisyon - self.nominal_net_pozisyon

    # ---- Başabaş için dayanak: DSO ---------------------------------------------
    # VADE MAKASI PANELİ KALDIRILDI. «Kaç gün kendi kesenden finanse ediyorsun» sorusunu
    # Alacak & Borç sekmesi ZATEN doğru yöntemle cevaplıyor (TahsilatAlacak.dso/.dpo,
    # «Nakit döngüsü: tahsilat Xg, ödeme Yg»). Buradaki makas iki «vadeye kalan gün»
    # ortalamasının farkıydı: canlıda 17−18 = 1 gün çıkıyor, işareti de o sekmenin
    # tersineydi. İki sekme aynı soruya çelişen cevap verince ikisine de güven gider
    # (kural 5: veri tekrarı yok; kural 3c).

    @property
    def basabas_olculdu(self) -> bool:
        """Tahsilat süresi ölçülebildi mi (satış yoksa ya da pencere kısaysa hayır).

        DSO ~0 da «ölçülemedi» sayılır: sıfır günde tahsil eden firmada başabaş
        farkı zaten sıfırdır ve «ölçülen tahsil süren — … %0,0» gibi anlamsız bir
        cümle üretiyordu (sentetik veriyle görüldü — _gun() 0'ı «—» basar).
        """
        return (self.dso is not None and self.donem_gun > 0
                and 0.5 <= self.dso <= self.donem_gun)

    @property
    def basabas_alt_sinir(self) -> bool:
        """
        DSO pencereden uzun: pencere ölçmeye yetmiyor, ancak «en az» denebilir.

        Kural 3: hesaplanamıyorsa tahmin edilmez, ölçülmüş tek yönlü sınır varsa o yazılır.
        """
        return (self.dso is not None and self.donem_gun > 0
                and self.dso > self.donem_gun)

    @property
    def basabas_dayanak_gun(self) -> float:
        """Başabaş farkının çapalandığı gün — pencere yetmiyorsa pencerenin kendisi."""
        if self.basabas_alt_sinir:
            return float(self.donem_gun)
        return float(self.dso or 0.0)

    # ---- Başabaş vade farkı ---------------------------------------------------
    @property
    def basabas_kendi_vaden(self) -> float:
        """Ölçülen tahsil süresinde başabaş kalmak için gereken fiyat farkı (%)."""
        return basabas_vade_farki(
            self.basabas_dayanak_gun, self.varsayim.yillik_iskonto_yuzde)

    @property
    def basabas_merdiven(self) -> list[tuple[int, float]]:
        return [(g, basabas_vade_farki(g, self.varsayim.yillik_iskonto_yuzde))
                for g in BASABAS_GUNLER]


def _oran(yuzde: float) -> float:
    return max(0.0, float(yuzde)) / 100.0


def bugunku_deger(tutar: float, gun: float, yillik_iskonto_yuzde: float) -> float:
    """Gelecekteki nominal tutarın bugünkü değeri (bileşik yıllık iskonto)."""
    nominal = max(0.0, float(tutar))
    if nominal < 0.005:
        return 0.0
    gun = max(0.0, float(gun))
    oran = _oran(yillik_iskonto_yuzde)
    if gun < 0.005 or oran < 0.0000001:
        return nominal
    return nominal / ((1.0 + oran) ** (gun / 365.0))


def basabas_vade_farki(gun: float, yillik_iskonto_yuzde: float) -> float:
    """
    Vadeli satarken peşin fiyatın kaç yüzde üstüne çıkılmalı ki başabaş kalınsın.

    İskonto oranı soyut kalıyor: «%45» rakamı sahibe bir şey söylemiyor. Somut hâli
    şudur — 90 gün vadeli satıyorsan peşin fiyatın %9,6 üstüne çıkmazsan, farkı
    kendi cebinden ödüyorsun. Bu, iskontonun tam tersi işlem (bugünkü değeri
    nominale çıkaran çarpan), o yüzden 1/PV değil (1+oran)^(gün/365).
    """
    gun = max(0.0, float(gun))
    oran = _oran(yillik_iskonto_yuzde)
    if gun < 0.005 or oran < 0.0000001:
        return 0.0
    return ((1.0 + oran) ** (gun / 365.0) - 1.0) * 100.0


def _cari_erimeleri(parcalar: list, sinif: str, yillik_iskonto_yuzde: float,
                    top_n: int = 10) -> list[CariErime]:
    """Cari bazında vade etkisi — en çok eriteni öne alır (bakiye sırası DEĞİL)."""
    kova: dict[str, dict] = {}
    for p in parcalar:
        if getattr(p, "sinif", "") != sinif or p.tutar <= 0.005:
            continue
        kod = getattr(p, "kod", "") or ""
        d = kova.setdefault(kod, {"unvan": getattr(p, "unvan", "") or kod,
                                  "nominal": 0.0, "pv": 0.0, "gun_agirlik": 0.0})
        d["nominal"] += p.tutar
        d["pv"] += bugunku_deger(p.tutar, p.vade_gun, yillik_iskonto_yuzde)
        d["gun_agirlik"] += max(0, p.vade_gun) * p.tutar
    out = [
        CariErime(kod=kod, unvan=d["unvan"], nominal=d["nominal"],
                  agirlikli_gun=(d["gun_agirlik"] / d["nominal"]) if d["nominal"] > 0.005 else 0.0,
                  vade_etkisi=d["nominal"] - d["pv"])
        for kod, d in kova.items()
    ]
    out = [c for c in out if c.vade_etkisi > 0.005]
    out.sort(key=lambda c: c.vade_etkisi, reverse=True)
    return out[:top_n]


def _deger_ozeti(parcalar: list, sinif: str, yillik_iskonto_yuzde: float) -> DegerOzet:
    ilgili = [p for p in parcalar if getattr(p, "sinif", "") == sinif and p.tutar > 0.005]
    nominal = sum(p.tutar for p in ilgili)
    if nominal < 0.005:
        return DegerOzet()
    pv = sum(bugunku_deger(p.tutar, p.vade_gun, yillik_iskonto_yuzde) for p in ilgili)
    agirlikli_gun = sum(max(0, p.vade_gun) * p.tutar for p in ilgili) / nominal
    return DegerOzet(
        nominal=nominal,
        bugunku_deger=pv,
        vade_etkisi=nominal - pv,
        agirlikli_gun=agirlikli_gun,
    )


def build_reel_deger_analizi(ta: TahsilatAlacak, v: ReelDegerVarsayim) -> ReelDegerAnalizi:
    """Açık cari kalemlerden vade etkisi analizini kurar."""
    parcalar = getattr(ta, "acik_vade_parcalari", []) or []
    o = v.yillik_iskonto_yuzde
    return ReelDegerAnalizi(
        varsayim=v,
        alacak=_deger_ozeti(parcalar, "customer", o),
        borc=_deger_ozeti(parcalar, "supplier", o),
        dso=getattr(ta, "dso", None),
        donem_gun=getattr(ta, "donem_gun", 0) or 0,
        gecikmis_alacak=getattr(ta, "alacak_gecikmis", 0.0) or 0.0,
        top_alacak_erime=_cari_erimeleri(parcalar, "customer", o),
        top_borc_erime=_cari_erimeleri(parcalar, "supplier", o),
    )


def reel_deger_csv(a: ReelDegerAnalizi) -> str:
    """Vade etkisi analizini Türkçe Excel uyumlu CSV'ye çevirir."""
    s = csv_sayi
    v = a.varsayim
    out = ["Bölüm;Kalem;Değer"]
    out.extend([
        f"VARSAYIM;Paranın yıllık maliyeti %;{s(v.yillik_iskonto_yuzde)}",
        f"ALACAK;Nominal;{s(a.alacak.nominal)}",
        f"ALACAK;Bugünkü ekonomik değer;{s(a.alacak.bugunku_deger)}",
        f"ALACAK;Vade maliyeti;{s(a.alacak.vade_etkisi)}",
        f"BORÇ;Nominal;{s(a.borc.nominal)}",
        f"BORÇ;Bugünkü ekonomik değer;{s(a.borc.bugunku_deger)}",
        f"BORÇ;Vade avantajı;{s(a.borc.vade_etkisi)}",
        f"NET;Nominal pozisyon;{s(a.nominal_net_pozisyon)}",
        f"NET;Reel pozisyon;{s(a.reel_net_pozisyon)}",
        f"NET;Vade etkisi;{s(a.net_vade_etkisi)}",
    ])
    if a.gecikmis_alacak > 0.005:
        out.append(f"ALACAK;Vade maliyeti alt sınır sebebi (vadesi geçmiş);{s(a.gecikmis_alacak)}")
    if a.basabas_olculdu:
        out.append(f"BAŞABAŞ VADE FARKI;Tahsil süresi (DSO, gün);{s(a.dso or 0.0)}")
        out.append(f"BAŞABAŞ VADE FARKI;Kendi tahsil sürende (%);{s(a.basabas_kendi_vaden)}")
    elif a.basabas_alt_sinir:
        out.append(f"BAŞABAŞ VADE FARKI;Tahsil süresi en az (gün);{s(float(a.donem_gun))}")
        out.append(f"BAŞABAŞ VADE FARKI;Kendi tahsil sürende en az (%);{s(a.basabas_kendi_vaden)}")
    else:
        out.append("BAŞABAŞ VADE FARKI;Tahsil süresi ölçülemedi;dönemde kredili satış yok")
    out.extend(f"BAŞABAŞ VADE FARKI;{g} gün (%);{s(y)}" for g, y in a.basabas_merdiven)
    # Ünvan csv_metin'den geçer — «;» içeren ünvan sütunları kaydırıyordu.
    out.extend(f"EN ÇOK ERİTEN MÜŞTERİ;{csv_metin(c.unvan)};{s(c.vade_etkisi)}"
               for c in a.top_alacak_erime)
    out.extend(f"EN ÇOK KAZANDIRAN SATICI;{csv_metin(c.unvan)};{s(c.vade_etkisi)}"
               for c in a.top_borc_erime)
    return "\r\n".join(out)
