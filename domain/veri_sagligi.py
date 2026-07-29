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
from domain.ortak import tr_sayi

KRITIK = "kritik"
UYARI = "uyari"
BILGI = "bilgi"

_ONEM_SIRA = {KRITIK: 0, UYARI: 1, BILGI: 2}

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
    # «Düzeltin» demek yetmez: hangi kayıt olduğu yazmazsa kullanıcı yüz binlerce satır
    # içinde onu bulamaz. Her satır Mikro'da evrakı açmaya yetecek kadar bilgi taşır.
    kayitlar: list[str] = field(default_factory=list)


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


def _aykiri_satir_metni(r: dict) -> str:
    """Bir aykırı satırı Mikro'da bulunabilecek şekilde tek satıra yazar."""
    def al(*adlar: str):
        for ad in adlar:
            v = r.get(ad, r.get(ad.upper()))
            if v not in (None, ""):
                return v
        return ""

    tarih = str(al("tarih"))[:10]
    # Seri boş + sıra 0 ise evrak no yok demektir; "0" yazmak kullanıcıyı yanıltır.
    seri = str(al("sth_evrakno_seri")).strip()
    sira = int(_f(al("sth_evrakno_sira")))
    evrak = f"{seri}{sira}" if (seri or sira) else str(al("sth_belge_no")).strip() or "?"
    stok = str(al("sth_stok_kod")) or "?"
    tip, ev = int(_f(al("sth_tip"))), int(_f(al("sth_evraktip")))
    # HANGİ ALAN aykırı, açıkça yazar. Canlıda «150 adet · 8.250 TL» satırı listeye
    # girdi (maliyet kolonu aykırıydı) ve bakan kişi haklı olarak «bunun nesi bozuk»
    # dedi. İşaretlenen alan söylenmeden liste güvenilirliğini kaybediyor.
    aykiri = [ad for ad, anahtar in (("tutar", "tutar_aykiri"),
                                     ("maliyet", "maliyet_aykiri"))
              if _f(al(anahtar)) >= 1]
    isaret = f"  ←  {' + '.join(aykiri)} aykırı" if aykiri else ""
    # Sayılar TEK TEK biçimlenir; cümlenin tamamında virgül→nokta değişimi
    # tl() çıktısını bozardı (bkz. domain.ortak.tr_sayi).
    return (f"{tarih}  ·  evrak {evrak}  ·  {stok}  ·  "
            f"{tr_sayi(_f(al('sth_miktar')))} adet  ·  tutar {tl(_f(al('sth_tutar')))}"
            f"  ·  maliyet {tl(_f(al('sth_maliyet_ana')))}  "
            f"(tip {tip}/evrak {ev}){isaret}")


def _bozuk_stok_kaydi(stok_rows: list[dict],
                      aykiri_rows: list[dict] | None = None) -> Bulgu | None:
    """
    Mal olamayacak kadar büyük stok hareketi satırı.

    Canlıda 13 böyle satır vardı; biri (07.12.2023, yevmiye 731) 2 adet mala 3,3
    TRİLYON TL taşıyordu ve o yılı içeren her rapor bundan zehirleniyordu.

    EŞİK BURADA DEĞİL, SORGUDA VE ÖLÇÜLEREK belirlenir (infra.mikro_fetch.AYKIRI_KAT):
    satır, dönemin ORTALAMA satırının on binlerce katıysa aykırıdır. Eskiden burada
    mutlak bir sınır vardı («satır başına 2 milyon TL») — bu program Mikro kullanan HER
    firmaya satılacak ve mutlak sınır küçük firmada hiçbir şey yakalamaz, büyük firmada
    gerçek faturayı bozuk ilan ederdi.
    """
    # Toplamlar sth_tutar'dan gelir; liste sth_maliyet_ana'da bozuk olanları da bulur.
    # Hangisi daha çok satır görüyorsa o yazılır — eksik saymak, saymamaktan kötüdür.
    ozet_adet = sum(_f(r.get("aykiri_adet", r.get("AYKIRI_ADET"))) for r in stok_rows or [])
    tutar = sum(_f(r.get("aykiri_tutar", r.get("AYKIRI_TUTAR"))) for r in stok_rows or [])
    adet = max(ozet_adet, len(aykiri_rows or []))
    if adet < 1:
        return None
    return Bulgu(
        kod="bozuk_stok", onem=KRITIK,
        baslik="Stok hareketlerinde hatalı kayıt var",
        etkisi=("Bu satırlar rapor toplamlarına ALINMADI — alınsaydı satış, alış ve "
                "kârlılık rakamlarınız gerçekte olmadığı kadar büyük görünürdü."),
        ne_yapmali=("Mikro'da bu kayıtları bulup düzeltin; düzeltilene kadar o dönemin "
                    "stok değeri hesaplanamaz."),
        olcum=f"{int(adet)} satır, toplam {tl(tutar)} — bir mal hareketi bu kadar olamaz",
        kayitlar=[_aykiri_satir_metni(r) for r in (aykiri_rows or [])])


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
    aykiri_rows: list[dict] | None = None,
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
        bulgular += [_bozuk_stok_kaydi(stok_rows, aykiri_rows),
                     _tanimsiz_evrak(stok_rows)]
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
    # Tek tek kayıtlar CSV'ye de girer: kullanıcı Excel'de süzüp Mikro'da açabilsin.
    kayitli = [b for b in vs.bulgular if b.kayitlar]
    if kayitli:
        out.append("")
        out.append("BULGU;KAYIT")
        for b in kayitli:
            for satir in b.kayitlar:
                out.append(f"{b.baslik.replace(';', ',')};{satir.replace(';', ',')}")
    return "\r\n".join(out)
