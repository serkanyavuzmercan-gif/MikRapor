"""
Veri Sağlığı — «bu rapordaki rakamlara güvenebilir miyim?»

BU BİR DENETİM RAPORU DEĞİLDİR. Okuyan kişi idarecidir; «sth_maliyet_ana kolonunun
doluluk oranı %89» cümlesi ona hiçbir şey söylemez. Her bulgu üç şeyi sade dille
söyler: ne olmuş, hangi rakamı bozuyor, ne yapılmalı.

BİR BULGU ANCAK İKİSİ BİRDEN DOĞRUYSA GÖSTERİLİR:
  (a) ekranda görülen bir rakamı bozuyor,
  (b) kullanıcının yapabileceği bir şey var.

Bu kural elemeyi sertleştirdi. «Satış satırlarının %11'inde maliyet yok» uyarısı
kaldırıldı: kendi metni bile «depodan geçen maldan hesaplanan marj bundan etkilenmez»
diyordu — yani hiçbir rakamı bozmuyordu. Tanımsız evrak tipi yalnız ÖNEMLİ tutarda
gösteriliyor; canlıda cironun %1'iydi ve kullanıcıya yapamayacağı bir iş veriyordu.
«Bize bildirin» gibi cümleler de yok: satılan bir üründe «biz» diye bir muhatap yok.

Neden var: bu programda çıkan her «bu rakam yanlış» şikâyeti, kovalandığında verinin
belirli bir yerindeki bozukluğa çıktı — işlenmemiş maliyet fişi, tek bir hatalı stok
kaydı, tanınmayan evrak tipi. Bunları bulan mantık zaten vardı ama teşhis
betiklerine dağılmıştı; kullanıcı çalıştırmıyordu. Burada toplanıyor.

Saf katman: ağ çağrısı yok, çekilmiş satırlar girer, bulgular çıkar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.mizan_bilanco import Bilanco, tl
from domain.ortak import to_float as _f

KRITIK = "kritik"
UYARI = "uyari"
BILGI = "bilgi"

_ONEM_SIRA = {KRITIK: 0, UYARI: 1, BILGI: 2}

# Bir mal hareketi satırının makul üst sınırı. Canlıda tek bir kayıt (2 adet mala
# 3,3 trilyon TL) bütün 2023 raporunu zehirliyordu.
_MAKUL_SATIR_TUTARI = 2_000_000.0

# Aktif ile pasif bu orandan fazla ayrışıyorsa mizan kendi içinde tutarsızdır.
# Bilinçli olarak GENİŞ: mizan sorgusu kapanış/açılış fişlerini eliyor, bu da küçük
# bir sapma bırakabiliyor. Dar tolerans her kullanıcıya sahte «kritik» gösterirdi.
_DENGE_TOLERANS = 0.01

# STOK_HAREKETLERI'nde tanıdığımız (tip, evraktip) çiftleri.
_BILINEN_EVRAK = {(0, 3), (0, 12), (1, 1), (1, 4), (1, 16)}

# Tanımsız hareket, toplam hareketin bu yüzdesine ulaşmıyorsa GÖSTERİLMEZ.
# Canlıda %1'di; kullanıcının yapabileceği bir şey yok ve gerçek bulguyu gölgeliyor.
_ONEMLI_PAY = 5.0


@dataclass
class Bulgu:
    """Tek bir veri sorunu — idarecinin okuyabileceği dilde."""

    kod: str
    onem: str
    baslik: str          # tek satır: ne olmuş
    etkisi: str          # hangi rakamlar bundan etkileniyor
    ne_yapmali: str
    olcum: str = ""      # varsa rakam


@dataclass
class VeriSagligi:
    bas: str = ""
    bit: str = ""
    bulgular: list[Bulgu] = field(default_factory=list)
    okunamayan: list[str] = field(default_factory=list)   # kontrol edilemeyen alanlar

    @property
    def kritik(self) -> int:
        return sum(1 for b in self.bulgular if b.onem == KRITIK)

    @property
    def uyari(self) -> int:
        return sum(1 for b in self.bulgular if b.onem == UYARI)

    @property
    def temiz(self) -> bool:
        return not self.bulgular

    def ozet(self) -> str:
        """Üst şeritte tek satır — idareci başka bir şey okumasa bile bunu okur."""
        if self.temiz:
            return "Veriniz sağlıklı — rakamları bozacak bir şey bulunamadı."
        parcalar = []
        if self.kritik:
            parcalar.append(f"{self.kritik} kritik")
        if self.uyari:
            parcalar.append(f"{self.uyari} uyarı")
        bilgi = len(self.bulgular) - self.kritik - self.uyari
        if bilgi:
            parcalar.append(f"{bilgi} not")
        return f"{len(self.bulgular)} bulgu: " + " · ".join(parcalar)


def _sirala(bulgular: list[Bulgu]) -> list[Bulgu]:
    return sorted(bulgular, key=lambda b: _ONEM_SIRA.get(b.onem, 9))


def _maliyet_kapanisi(b: Bilanco) -> Bulgu | None:
    """
    Eksik «621 SMM / 153 Ticari Mallar» fişi — bu programın en sık karşılaştığı sorun.

    Fişin iki ayağı var: 621 borçlanmayınca kâr, 153 alacaklanmayınca stok aynı
    tutarda şişer. Canlıda 2026 stoğu %52 artmış görünürken fiilen %42 azalmıştı.
    """
    if not b.maliyet_eksik:
        return None
    return Bulgu(
        kod="maliyet_kapanisi", onem=KRITIK,
        baslik="Satışların maliyeti muhasebeye işlenmemiş",
        etkisi=("Kâr olduğundan YÜKSEK, stok olduğundan YÜKSEK görünür — ikisi de aynı "
                "tutarda. Özkaynak, aktif toplam ve bunlardan türeyen bütün oranlar "
                "(cari oran, borç/özkaynak, stok devir hızı) bu yüzden boş bırakılır."),
        ne_yapmali=("Mali müşavirinize sorun: maliyet kaydını yıl sonunda mı yapıyor, "
                    "ay sonlarında da yapılabilir mi. Yıl içinde bankaya/ortaklara "
                    "verdiğiniz bilanço bu yüzden yanlış görünüyor."),
        olcum="62 hesabında bu dönemde hareket yok")


def _mizan_dengesi(b: Bilanco) -> Bulgu | None:
    """Aktif ≠ pasif ise mizanın kendisi tutarsız; hiçbir bilanço rakamı güvenilmez."""
    toplam = max(abs(b.aktif_toplam), abs(b.pasif_toplam))
    if toplam < 0.005:
        return None
    fark = abs(b.aktif_toplam - b.pasif_toplam)
    if fark / toplam <= _DENGE_TOLERANS:
        return None
    return Bulgu(
        kod="mizan_denge", onem=UYARI,
        baslik="Muhasebe mizanında varlıklar ile kaynaklar eşit değil",
        etkisi="Bilançodan gelen rakamlar (stok, özkaynak, aktif toplam) şüpheli olabilir.",
        ne_yapmali=("Mali müşavirinize mizanı kontrol ettirin. Küçük farklar dönem içi "
                    "eksik fişten olabilir; büyük fark gerçek bir hatadır."),
        olcum=f"Aktif {tl(b.aktif_toplam)} · Pasif {tl(b.pasif_toplam)} · "
              f"fark {tl(fark)}")


def _bozuk_stok_kaydi(stok_rows: list[dict]) -> Bulgu | None:
    """
    Satır başı tutarı mal olamayacak kadar büyük bir hareket türü.

    Canlıda tek bir kayıt (07.12.2023, yevmiye 731) 3,3 trilyon TL taşıyordu ve o
    yılı içeren her rapor bundan zehirleniyordu.
    """
    supheli: list[tuple[float, int, int]] = []
    for r in stok_rows or []:
        adet = _f(r.get("adet", r.get("ADET")))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        if adet <= 0:
            continue
        birim = tutar / adet
        if birim > _MAKUL_SATIR_TUTARI:
            supheli.append((birim, int(_f(r.get("sth_tip", r.get("STH_TIP")))),
                            int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP"))))))
    if not supheli:
        return None
    supheli.sort(reverse=True)
    birim, _tip, _ev = supheli[0]
    return Bulgu(
        kod="bozuk_stok", onem=KRITIK,
        baslik="Stok hareketlerinde hatalı bir kayıt var",
        etkisi=("Satış ya da alış toplamınız gerçekte olmadığı kadar büyük görünüyor; "
                "kârlılık ve stok rakamları bu tek kayıt yüzünden anlamsızlaşıyor."),
        ne_yapmali=("Mikro'da bu evrak tipindeki en büyük kaydı bulup düzeltin — "
                    "tek bir hatalı satır bütün dönemi bozuyor."),
        olcum=f"Satır başına ortalama {tl(birim)} — bir mal hareketi bu kadar olamaz")


def _tanimsiz_evrak(stok_rows: list[dict]) -> Bulgu | None:
    """Sınıflandıramadığımız hareket türü: satış mı alış mı bilmiyoruz, dışarıda kalıyor."""
    bilinmeyen: list[tuple[float, int, int]] = []
    toplam_hareket = 0.0
    for r in stok_rows or []:
        tip = int(_f(r.get("sth_tip", r.get("STH_TIP"))))
        ev = int(_f(r.get("sth_evraktip", r.get("STH_EVRAKTIP"))))
        tutar = _f(r.get("tutar", r.get("TUTAR")))
        toplam_hareket += abs(tutar)
        if (tip, ev) not in _BILINEN_EVRAK and abs(tutar) > 0.005:
            bilinmeyen.append((abs(tutar), tip, ev))
    if not bilinmeyen:
        return None
    bilinmeyen.sort(reverse=True)
    disarida = sum(t for t, _, _ in bilinmeyen)
    # ÖNEMSİZ TUTAR GÖSTERİLMEZ. Canlıda tanımsız tür cironun %1'iydi; onu ekrana
    # koymak kullanıcıya yapamayacağı bir iş vermek ve gerçek bulguyu gölgelemekti.
    if toplam_hareket <= 0.005 or disarida / toplam_hareket * 100 < _ONEMLI_PAY:
        return None
    _, _tip, ev = bilinmeyen[0]
    return Bulgu(
        kod="tanimsiz_evrak", onem=UYARI,
        baslik="Satış/alış sayılmayan büyük bir hareket türü var",
        etkisi=("Bu tutar fiili kârlılık hesabının dışında kalıyor; satış ve alış "
                "rakamlarınız bu kadar eksik."),
        ne_yapmali=(f"Mikro'da bu hareketi açıp ne olduğuna bakın (evrak tipi {ev}). "
                    "Gerçekten satış ya da alışsa rakamlarınız eksik demektir."),
        olcum=f"{tl(disarida)} · hareketlerin %{disarida / toplam_hareket * 100:.0f}'i")



def build_veri_sagligi(
    *,
    bas: str = "",
    bit: str = "",
    bilanco: Bilanco | None = None,
    stok_rows: list[dict] | None = None,
    okunamayan: list[str] | None = None,
) -> VeriSagligi:
    """
    Çekilmiş satırlardan bulguları kurar (saf).

    Okunamayan kaynak SESSİZCE ATLANMAZ: `okunamayan` listesine yazılır ve ekranda
    «kontrol edilemedi» diye görünür. Yoksa kullanıcı, bakılamayan bir şeyi temiz
    sanar — bu, hatanın kendisinden daha kötüdür.
    """
    vs = VeriSagligi(bas=bas, bit=bit, okunamayan=list(okunamayan or []))
    bulgular: list[Bulgu | None] = []
    if bilanco is not None:
        bulgular += [_maliyet_kapanisi(bilanco), _mizan_dengesi(bilanco)]
    if stok_rows is not None:
        bulgular += [_bozuk_stok_kaydi(stok_rows), _tanimsiz_evrak(stok_rows)]
    vs.bulgular = _sirala([b for b in bulgular if b is not None])
    return vs


def veri_sagligi_csv(vs: VeriSagligi) -> str:
    out = ["BÖLÜM;DEĞER", f"DÖNEM;{vs.bas} – {vs.bit}", f"ÖZET;{vs.ozet()}", ""]
    out.append("ÖNEM;BULGU;ÖLÇÜM;ETKİSİ;NE YAPMALI")
    for b in vs.bulgular:
        out.append(";".join(x.replace(";", ",") for x in
                            (b.onem, b.baslik, b.olcum, b.etkisi, b.ne_yapmali)))
    for ad in vs.okunamayan:
        out.append(f"kontrol edilemedi;{ad};;;")
    return "\r\n".join(out)
