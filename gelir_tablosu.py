"""
Gelir Tablosu (Kâr/Zarar) motoru — Mikro GL'den, dönem (başlangıç–bitiş) bazlı.

Tek Düzen Hesap Planı 6xx hesaplarından şelale (waterfall) gelir tablosu kurar:
  Brüt Satışlar (60) − İndirimler (61) = Net Satışlar
  Net Satışlar − SMM (62) = Brüt Satış Kârı
  − Faaliyet Giderleri (63) = Faaliyet Kârı
  ± Diğer Faaliyet (64/65) − Finansman (66) = Olağan Kâr
  ± Olağandışı (67/68) = Dönem Kârı
  − Vergi (691) = Dönem Net Kârı/Zararı

İşaret kuralı: her hesabın "gelir-tablosu tutarı" = −bakiye (= alacak−borç). Böylece gelir +,
gider/maliyet − olur ve şelale toplamı doğal akar. Dönem Net Kârı, bilançonun donem_kz'siyle
aynı 6xx kümesinden geldiği için BİREBİR tutmalıdır (yerleşik mutabakat). 690/692 kapanış
aynası olduğundan şelaleye DAHİL EDİLMEZ (çift sayımı önler).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from mizan_bilanco import ana_hesap, tl

HESAP_ADLARI_GELIR: dict[str, str] = {
    "600": "Yurtiçi Satışlar", "601": "Yurtdışı Satışlar", "602": "Diğer Gelirler",
    "610": "Satıştan İadeler (-)", "611": "Satış İskontoları (-)", "612": "Diğer İndirimler (-)",
    "620": "Satılan Mamuller Maliyeti (-)", "621": "Satılan Ticari Mallar Maliyeti (-)",
    "622": "Satılan Hizmet Maliyeti (-)", "623": "Diğer Satışların Maliyeti (-)",
    "630": "Araştırma ve Geliştirme Giderleri (-)", "631": "Pazarlama, Satış ve Dağıtım Giderleri (-)",
    "632": "Genel Yönetim Giderleri (-)",
    "640": "İştiraklerden Temettü Gelirleri", "641": "Bağlı Ortaklıklardan Temettü Gelirleri",
    "642": "Faiz Gelirleri", "643": "Komisyon Gelirleri", "644": "Konusu Kalmayan Karşılıklar",
    "645": "Menkul Kıymet Satış Kârları", "646": "Kambiyo Kârları", "647": "Reeskont Faiz Gelirleri",
    "648": "Enflasyon Düzeltmesi Kârları", "649": "Diğer Olağan Gelir ve Kârlar",
    "653": "Komisyon Giderleri (-)", "654": "Karşılık Giderleri (-)",
    "655": "Menkul Kıymet Satış Zararları (-)", "656": "Kambiyo Zararları (-)",
    "657": "Reeskont Faiz Giderleri (-)", "658": "Enflasyon Düzeltmesi Zararları (-)",
    "659": "Diğer Olağan Gider ve Zararlar (-)",
    "660": "Kısa Vadeli Borçlanma Giderleri (-)", "661": "Uzun Vadeli Borçlanma Giderleri (-)",
    "671": "Önceki Dönem Gelir ve Kârları", "679": "Diğer Olağandışı Gelir ve Kârlar",
    "680": "Çalışmayan Kısım Gider ve Zararları (-)", "681": "Önceki Dönem Gider ve Zararları (-)",
    "689": "Diğer Olağandışı Gider ve Zararlar (-)",
    "691": "Dönem Kârı Vergi ve Diğer Yasal Yük. Karşılıkları (-)",
}


def _f(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _hesap_adi(kod: str) -> str:
    return HESAP_ADLARI_GELIR.get(kod, f"{kod} Hesabı")


def yuzde(v: float) -> str:
    """12.5 -> '%12,5' (Türkçe ondalık)."""
    return ("%" + f"{v:.1f}").replace(".", ",")


@dataclass
class GTSatir:
    """Gelir tablosunun bir görüntü satırı."""
    tip: str            # "bolum" | "hesap" | "sonuc"
    etiket: str
    tutar: float | None = None  # None ise (yalnız başlık)


@dataclass
class GelirTablosu:
    bas: str = ""
    bit: str = ""
    satirlar: list[GTSatir] = field(default_factory=list)
    net_satislar: float = 0.0
    smm: float = 0.0           # Satışların Maliyeti (62), işaretli (negatif veya 0)
    brut_kar: float = 0.0
    faaliyet_kari: float = 0.0
    donem_kari: float = 0.0
    net_kar: float = 0.0
    hesap_sayisi: int = 0

    @property
    def maliyet_eksik(self) -> bool:
        """Satış var ama SMM (62) ≈ 0 → maliyet kapanışı yapılmamış; kâr şişik görünür."""
        return self.net_satislar > 0 and abs(self.smm) < 0.05 * self.net_satislar

    @property
    def brut_marj(self) -> float:
        return (self.brut_kar / self.net_satislar * 100) if self.net_satislar else 0.0

    @property
    def faaliyet_marj(self) -> float:
        return (self.faaliyet_kari / self.net_satislar * 100) if self.net_satislar else 0.0

    @property
    def net_marj(self) -> float:
        return (self.net_kar / self.net_satislar * 100) if self.net_satislar else 0.0


def build_gelir_tablosu(rows: list[dict], bas: str = "", bit: str = "") -> GelirTablosu:
    """
    6xx mizan satırlarından (hesap_kodu, borc, alacak) dönem gelir tablosu kurar.

    tutar = −bakiye = alacak − borç (gelir +, gider −). Şelale akışıyla ara sonuçlar hesaplanır.
    """
    grup: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        kod = r.get("hesap_kodu") or r.get("HESAP_KODU") or r.get("fis_hesap_kod")
        ana = ana_hesap(kod)
        if not ana.startswith("6"):
            continue
        grup[ana][0] += _f(r.get("borc", r.get("BORC")))
        grup[ana][1] += _f(r.get("alacak", r.get("ALACAK")))

    # ana hesap -> tutar (−bakiye)
    tutar: dict[str, float] = {}
    for ana, (borc, alacak) in grup.items():
        tutar[ana] = alacak - borc  # = −bakiye

    def grup_satirlari(pref2: str) -> list[tuple[str, float]]:
        out = [(k, tutar[k]) for k in sorted(tutar) if k[:2] == pref2 and abs(tutar[k]) >= 0.005]
        return out

    def grup_toplam(pref2: str) -> float:
        return sum(tutar[k] for k in tutar if k[:2] == pref2)

    gt = GelirTablosu(bas=bas, bit=bit, hesap_sayisi=len(grup))
    S = gt.satirlar

    def bolum(baslik: str, pref2: str) -> float:
        satirlar = grup_satirlari(pref2)
        if not satirlar:
            return 0.0
        S.append(GTSatir("bolum", baslik))
        for kod, t in satirlar:
            S.append(GTSatir("hesap", f"{kod}  {_hesap_adi(kod)}", t))
        return grup_toplam(pref2)

    def sonuc(etiket: str, deger: float) -> None:
        S.append(GTSatir("sonuc", etiket, deger))

    # A. Brüt Satışlar − İndirimler = Net Satışlar
    bolum("BRÜT SATIŞLAR", "60")
    bolum("SATIŞ İNDİRİMLERİ (-)", "61")
    net_satislar = grup_toplam("60") + grup_toplam("61")
    sonuc("NET SATIŞLAR", net_satislar)

    # B. − SMM = Brüt Satış Kârı
    bolum("SATIŞLARIN MALİYETİ (-)", "62")
    brut_kar = net_satislar + grup_toplam("62")
    sonuc("BRÜT SATIŞ KÂRI/ZARARI", brut_kar)

    # C. − Faaliyet Giderleri = Faaliyet Kârı
    bolum("FAALİYET GİDERLERİ (-)", "63")
    faaliyet_kari = brut_kar + grup_toplam("63")
    sonuc("FAALİYET KÂRI/ZARARI", faaliyet_kari)

    # D. ± Diğer Faaliyet ± Finansman = Olağan Kâr
    bolum("DİĞER FAAL. OLAĞAN GELİR VE KÂRLAR", "64")
    bolum("DİĞER FAAL. OLAĞAN GİDER VE ZARARLAR (-)", "65")
    bolum("FİNANSMAN GİDERLERİ (-)", "66")
    olagan_kar = faaliyet_kari + grup_toplam("64") + grup_toplam("65") + grup_toplam("66")
    sonuc("OLAĞAN KÂR/ZARAR", olagan_kar)

    # E. ± Olağandışı = Dönem Kârı
    bolum("OLAĞANDIŞI GELİR VE KÂRLAR", "67")
    bolum("OLAĞANDIŞI GİDER VE ZARARLAR (-)", "68")
    donem_kari = olagan_kar + grup_toplam("67") + grup_toplam("68")
    sonuc("DÖNEM KÂRI/ZARARI", donem_kari)

    # F. − Vergi (691) = Dönem Net Kârı  (690/692 kapanış aynası → hariç)
    vergi = tutar.get("691", 0.0)
    if abs(vergi) >= 0.005:
        S.append(GTSatir("bolum", "DÖNEM KÂRI VERGİ KARŞILIKLARI (-)"))
        S.append(GTSatir("hesap", f"691  {_hesap_adi('691')}", vergi))
    net_kar = donem_kari + vergi
    sonuc("DÖNEM NET KÂRI/ZARARI", net_kar)

    gt.net_satislar = net_satislar
    gt.smm = grup_toplam("62")
    gt.brut_kar = brut_kar
    gt.faaliyet_kari = faaliyet_kari
    gt.donem_kari = donem_kari
    gt.net_kar = net_kar
    return gt


def gelir_tablosu_csv(gt: GelirTablosu) -> str:
    """Gelir tablosunu CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    def s(v: float) -> str:
        return f"{v:.2f}".replace(".", ",")

    out = ["Tür;Açıklama;Tutar (TL)"]
    out.append(f"DÖNEM;{gt.bas} - {gt.bit};")
    for r in gt.satirlar:
        tip = {"bolum": "Bölüm", "hesap": "Hesap", "sonuc": "Sonuç"}.get(r.tip, r.tip)
        tutar = "" if r.tutar is None else s(r.tutar)
        # ; ve yeni satırları temizle (CSV bütünlüğü)
        etiket = r.etiket.replace(";", ",").replace("\n", " ").strip()
        out.append(f"{tip};{etiket};{tutar}")
    out.append("")
    out.append(f"Brüt marj;{yuzde(gt.brut_marj)};")
    out.append(f"Faaliyet marj;{yuzde(gt.faaliyet_marj)};")
    out.append(f"Net marj;{yuzde(gt.net_marj)};")
    if gt.maliyet_eksik:
        out.append("UYARI;Satışların Maliyeti (62) ~0 - maliyet kapanışı yapılmamış olabilir; kâr şişik;")
    return "\r\n".join(out)


# --- Metin raporu (CLI/doğrulama) ---

def gelir_tablosu_metni(gt: GelirTablosu) -> str:
    out = [f"GELİR TABLOSU — {gt.bas} … {gt.bit}", "=" * 60]
    for s in gt.satirlar:
        if s.tip == "bolum":
            out.append(f"\n{s.etiket}")
        elif s.tip == "hesap":
            out.append(f"   {s.etiket:<46} {tl(s.tutar):>16}")
        else:  # sonuc
            out.append(f"{'─' * 60}\n{s.etiket:<46} {tl(s.tutar):>16}")
    out.append("=" * 60)
    out.append(f"Brüt marj {yuzde(gt.brut_marj)} · Faaliyet marj {yuzde(gt.faaliyet_marj)} · "
               f"Net marj {yuzde(gt.net_marj)}")
    return "\n".join(out)
