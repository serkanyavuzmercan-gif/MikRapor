"""
Mukayese & Oranlar — aylık operasyonel trend + bilanço oranları.

Aylık seri Nakit & Kârlılık motorunun AyTrend listesinden gelir; finansal oranlar
TDHP bilançosundan (dönen/KVYK/özkaynak) hesaplanır. Saf fonksiyon — ağ/GUI yok.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.gercek_durum import AyTrend
from domain.mizan_bilanco import Bilanco
from domain.ortak import csv_sayi, yuzde
from domain.terimler import sade_oran


@dataclass
class FinansalOran:
    """Tek bir oran satırı (ad, değer, birim, kısa yorum)."""
    kod: str
    ad: str
    deger: float | None
    birim: str = "x"          # "x" | "%" | "gün"
    aciklama: str = ""
    # Değer «—» ise NEDEN «—» olduğu — kural 2: sebep rakamın YANINDA söylenir.
    # Eskiden sebep yalnız bilanço özet kartındaki uyarıda yazıyordu; oran panelinde
    # yedi satırın beşi açıklamasız çizgiydi ve kullanıcı «neden boş ki bunlar?» diye
    # sordu (canlı demo). Boş değerin sebebi artık satırın kendisinde taşınır.
    sebep: str = ""

    def metin(self) -> str:
        if self.deger is None:
            return "—"
        if self.birim == "%":
            return yuzde(self.deger)
        if self.birim == "gün":
            return f"{self.deger:.0f} gün"
        return f"{self.deger:.2f}".replace(".", ",")


@dataclass
class TrendRapor:
    bas: str = ""
    bit: str = ""
    asof: str = ""
    aylik: list[AyTrend] = field(default_factory=list)
    # Grafik için daha uzun geçmiş (seçili dönem kısa olsa da trend görünsün).
    # KPI toplamları DAİMA `aylik`ten (seçili dönem) gelir — çelişki olmasın.
    aylik_gecmis: list[AyTrend] = field(default_factory=list)
    oranlar: list[FinansalOran] = field(default_factory=list)
    # Bilanço özet (oran hesabı kaynakları)
    donen: float = 0.0
    duran: float = 0.0
    kvyk: float = 0.0
    uvyk: float = 0.0
    ozkaynak: float = 0.0
    nakit: float = 0.0
    alacak: float = 0.0
    stok: float = 0.0
    aktif_toplam: float = 0.0
    # Satışın maliyeti (62) işlenmemiş: stok DA özkaynak DA aynı tutarda şişik.
    # Rakamı sessizce basmak yerine yanına ne olduğunu yazmak için taşınır.
    maliyet_eksik: bool = False

    @property
    def ay_sayisi(self) -> int:
        return len(self.aylik)

    @property
    def toplam_satis(self) -> float:
        return sum(a.satis for a in self.aylik)

    @property
    def toplam_brut(self) -> float:
        return sum(a.brut for a in self.aylik)

    @property
    def toplam_nakit_net(self) -> float:
        return sum(a.nakit_net for a in self.aylik)


# Tek cümle, üç yerde (ekran, PDF, CSV): mekanizmayı söyler, suçlamaz.
# «Kâr şişik» uyarısı tek başına yetmiyordu — kullanıcı stoğun da aynı fişten
# şiştiğini bilmediği için mizan stoğunu gerçek sanıp «bu artış imkânsız» dedi.
MALIYET_EKSIK_UYARI = (
    "Satışların maliyeti (62) bu dönemde muhasebeye işlenmemiş. Her satış "
    "«621 SMM / 153 Ticari Mallar» fişini gerektirir; bu fiş atılmadığı için stok "
    "azalmamış, kâr da azalmamış — İKİSİ DE AYNI TUTARDA ŞİŞİK. Stoğa ve özkaynağa "
    "dayanan oranlar bu yüzden boş bırakıldı. Asit-Test etkilenmez."
)


def _bolum_toplam(satirlar: list, digit: str) -> float:
    return sum(s.tutar for s in satirlar if s.ana[:1] == digit)


def _ana_toplam(satirlar: list, ana_kodlar: set[str]) -> float:
    return sum(s.tutar for s in satirlar if s.ana in ana_kodlar)


# Boş oranların sebepleri — üç yerde (ekran, PDF, CSV) aynı cümle.
# Satır başına düşen sebep KISA tutulur (yedi satırda tekrar ediyor, kural 4);
# mekanizmanın tam anlatımı MALIYET_EKSIK_UYARI'da, bilanço özetinin altında.
MALIYET_SEBEP = "62 işlenmemiş — stok/özkaynak şişik olduğundan hesaplanmadı"
OZKAYNAK_EKSI_SEBEP = ("özkaynak eksi: borçlar işletmenin tamamını aşmış — oran "
                       "bu durumda anlamını yitirir")
PAYDA_SIFIR_SEBEP = "payda sıfır — bilançoda bu kalem yok"


def build_finansal_oranlar(b: Bilanco) -> tuple[list[FinansalOran], dict[str, float]]:
    """Bilanço satırlarından klasik TDHP oranları."""
    donen = _bolum_toplam(b.aktif, "1")
    duran = _bolum_toplam(b.aktif, "2")
    kvyk = _bolum_toplam(b.pasif, "3")
    uvyk = _bolum_toplam(b.pasif, "4")
    ozkaynak = _bolum_toplam(b.pasif, "5") + b.donem_kz
    nakit = _ana_toplam(b.aktif, {"100", "101", "102", "108"})
    alacak = _ana_toplam(b.aktif, {"120", "121", "126"})
    stok = _ana_toplam(b.aktif, {"150", "151", "152", "153", "157", "159"})
    aktif = b.aktif_toplam
    yabanci = kvyk + uvyk

    def oran(pay: float, payda: float) -> float | None:
        if abs(payda) < 0.005:
            return None
        return pay / payda

    def yuz(pay: float, payda: float) -> float | None:
        r = oran(pay, payda)
        return None if r is None else r * 100.0

    def oz_orani(pay: float) -> float | None:
        """
        Özkaynağa BÖLEN oran; özkaynak eksiyken hesaplanmaz.

        Eksi paydada sonuç da eksi çıkar ve «borcum az» gibi okunur — oysa tam tersi,
        özkaynak tükenmiştir. Canlıda «Borç / Özkaynak -21,78» yazıyordu; aynı raporun
        mukayese tablosu ise doğru davranıp «—» diyordu. İki yerde iki farklı kural,
        aynı sayfada çelişki. Kural artık tek: özkaynak pozitif değilse bu oran yok.
        """
        return oran(pay, ozkaynak) if ozkaynak > 0.005 else None

    def stok_kirli(deger: float | None) -> tuple[float | None, str]:
        """
        Satışın maliyeti işlenmemişse stoğa dayanan oran GÖSTERİLMEZ — sebebiyle.

        Her satış «621 SMM / 153 Ticari Mallar» fişini gerektirir. Bu fiş atılmayınca
        153 hiç azalmaz, 621 hiç borçlanmaz: stok da kâr da AYNI tutarda şişer. Canlıda
        2026'da 62 hiç girilmemişti; mizan stoğu 21,5 milyon TL (459 bin USD) diyordu,
        işlenmemiş ~13,4 milyonluk maliyet düşülünce gerçek stok ~8,1 milyon TL
        (174 bin USD) çıkıyordu. Yani stok %52 ARTMIŞ görünürken fiilen %42 AZALMIŞTI —
        yön bile ters. Kullanıcı «bu kadar artmış olamaz» derken haklıydı.

        Bu yüzden stoğa ya da özkaynağa dayanan oranlar bu durumda boş bırakılır.
        Asit-Test dokunulmaz: (dönen − stok) şişkinliği zaten götürür.
        """
        if b.maliyet_eksik:
            return None, MALIYET_SEBEP
        if deger is None:
            return None, PAYDA_SIFIR_SEBEP
        return deger, ""

    def kirli_oran(kod: str, ad: str, ham: float | None, birim: str = "x",
                   *, ozkaynakli: bool = False) -> FinansalOran:
        deger, sebep = stok_kirli(ham)
        # Maliyet temizken bile özkaynak eksiyse sebep o — daha özgül olan yazılır.
        if deger is None and not b.maliyet_eksik and ozkaynakli and ozkaynak <= 0.005:
            sebep = OZKAYNAK_EKSI_SEBEP
        return FinansalOran(kod, ad, deger, birim, sade_oran(kod), sebep=sebep)

    def duz_oran(kod: str, ad: str, deger: float | None, birim: str = "x") -> FinansalOran:
        return FinansalOran(kod, ad, deger, birim, sade_oran(kod),
                            sebep="" if deger is not None else PAYDA_SIFIR_SEBEP)

    # Açıklamalar formül tekrarı değil, sade dilde (bkz. domain.terimler).
    oranlar = [
        kirli_oran("cari", "Cari Oran", oran(donen, kvyk)),
        duz_oran("asit", "Asit-Test (Likidite)", oran(donen - stok, kvyk)),
        duz_oran("nakit_oran", "Nakit Oranı", oran(nakit, kvyk)),
        kirli_oran("borc_oz", "Borç / Özkaynak", oz_orani(yabanci), ozkaynakli=True),
        kirli_oran("oz_oran", "Özkaynak Oranı", yuz(ozkaynak, aktif), "%"),
        kirli_oran("kv_oran", "Kısa Vadeli Borç Oranı", yuz(kvyk, aktif), "%"),
        kirli_oran("donen_oran", "Dönen Varlık Oranı", yuz(donen, aktif), "%"),
    ]
    ozet = {
        "donen": donen, "duran": duran, "kvyk": kvyk, "uvyk": uvyk,
        "ozkaynak": ozkaynak, "nakit": nakit, "alacak": alacak, "stok": stok,
        "aktif_toplam": aktif,
    }
    return oranlar, ozet


def build_trend(
    *,
    aylik: list[AyTrend] | None = None,
    aylik_gecmis: list[AyTrend] | None = None,
    bilanco: Bilanco | None = None,
    bas: str = "",
    bit: str = "",
) -> TrendRapor:
    """
    Aylık trend + (varsa) bilanço oranlarından TrendRapor üretir.

    `aylik` seçili dönemdir ve KPI toplamlarının tek kaynağıdır. `aylik_gecmis`
    yalnız grafiğe daha uzun bir pencere (ör. son 12 ay) vermek içindir; verilmezse
    grafik de seçili dönemi gösterir.
    """
    t = TrendRapor(bas=bas, bit=bit, asof=bit or (bilanco.asof if bilanco else ""))
    t.aylik = list(aylik or [])
    t.aylik_gecmis = list(aylik_gecmis or [])
    if bilanco is not None:
        t.asof = bilanco.asof or t.asof
        oranlar, ozet = build_finansal_oranlar(bilanco)
        t.oranlar = oranlar
        t.donen = ozet["donen"]
        t.duran = ozet["duran"]
        t.kvyk = ozet["kvyk"]
        t.uvyk = ozet["uvyk"]
        t.ozkaynak = ozet["ozkaynak"]
        t.nakit = ozet["nakit"]
        t.alacak = ozet["alacak"]
        t.stok = ozet["stok"]
        t.aktif_toplam = ozet["aktif_toplam"]
        t.maliyet_eksik = bilanco.maliyet_eksik
    return t


def trend_csv(t: TrendRapor) -> str:
    s = csv_sayi
    out = [
        "BÖLÜM;KALEM;DEĞER",
        f"DÖNEM;Başlangıç;{t.bas}",
        f"DÖNEM;Bitiş;{t.bit}",
        f"DÖNEM;Bilanço tarihi;{t.asof}",
    ]
    for o in t.oranlar:
        # Kural 2: «—» tek başına yazılmaz, sebebi yanında gider.
        deger = o.metin() if not o.sebep else f"{o.metin()} ({o.sebep})"
        out.append(f"ORAN;{o.ad};{deger}")
    out.append(f"BİLANÇO;Dönen varlıklar;{s(t.donen)}")
    out.append(f"BİLANÇO;KVYK;{s(t.kvyk)}")
    out.append(f"BİLANÇO;Özkaynak;{s(t.ozkaynak)}")
    out.append(f"BİLANÇO;Nakit;{s(t.nakit)}")
    out.append(f"BİLANÇO;Alacak;{s(t.alacak)}")
    out.append(f"BİLANÇO;Stok;{s(t.stok)}"
               + (" (ŞİŞİK — aşağıdaki uyarı)" if t.maliyet_eksik else ""))
    if t.maliyet_eksik:
        out.append(f"UYARI;{MALIYET_EKSIK_UYARI};")
    for a in t.aylik:
        out.append(f"AYLIK;{a.ay} Satış;{s(a.satis)}")
        out.append(f"AYLIK;{a.ay} Alış;{s(a.alis)}")
        out.append(f"AYLIK;{a.ay} Brüt;{s(a.brut)}")
        out.append(f"AYLIK;{a.ay} Nakit net;{s(a.nakit_net)}")
    out.append(
        "KAYNAK;Aylık Satış / Alış / Brüt = STOK_HAREKETLERİ operasyonel hareketleri. "
        "Nakit net = banka/kasa hareketleri."
    )
    out.append(
        f"NOT;Aylık bölüm yalnız seçili pencereyi kapsar: {t.bas}–{t.bit}. "
        "İlk ve son ay kısmi olabilir; bu satırları tam ay gibi kıyaslamayın."
    )
    return "\n".join(out) + "\n"
