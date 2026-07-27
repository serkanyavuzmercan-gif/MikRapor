"""
Yapay Zekâ Yorumu — rapor verisini paketleyen ve yorumu taşıyan saf katman.

Burada ağ çağrısı YOKTUR (bkz. infra/ai_client.py). Bu modül yalnız:
  • seçili dönemin tüm rapor verisini tek bir metin pakete çevirir (build_ai_veri_paketi),
  • modele verilecek yönergeyi tutar (SISTEM_PROMPT),
  • dönen yorumu taşır (AiYorum) ve CSV'ye çevirir.

Paket, her raporun kendi CSV üreticisinden kurulur — ekranda gördüğün rakamla modele
giden rakam aynı kaynaktan gelsin diye. Cari listeleri kırpılmaz: kullanıcı ham veri
paylaşımını açıkça onayladığında ünvanlar dâhil tüm kırılım gider.

ÇOK YILLI ANALİZ: Mikro'nun tek veritabanında birkaç yıl birden durabilir. Seçilen
aralık birden çok yıl kapsıyorsa EN YENİ yıl ham detayıyla, önceki yıllar birkaç
satırlık kapanış özetiyle (YilKapanis) gider — 5 yılın ham cari kırılımı hem girdi
sınırını aşar hem de modeli detayda boğar. Üst sınır AZAMI_YIL'dir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from domain.ortak import csv_sayi

# Modelin sağlıklı yorumlayabildiği en geniş aralık. Bunun ötesi hem girdi sınırını
# zorlar hem de yorumu yüzeyselleştirir; kullanıcı uyarılıp en yeni yıllara kırpılır.
AZAMI_YIL = 5

# Model, finans okuryazarlığı olmayan bir KOBİ sahibine yazıyor. Yönerge bilinçli olarak
# "ne yapmalıyım" odaklı: teşhis değil, karar. Uydurma rakamı önlemek için veri dışına
# çıkmaması ve eksik veriyi eksik demesi ayrıca istenir.
SISTEM_PROMPT = """\
Sen bir KOBİ'nin mali danışmanısın. Karşındaki kişi işini iyi bilir ama finans \
okuryazarı DEĞİLDİR: "cari oran", "DSO", "işletme sermayesi" gibi terimleri bilmez.

Sana bir Türk şirketinin muhasebe ve cari verisi CSV bölümleri hâlinde verilecek. Bu \
veriye bakarak Türkçe bir yönetim yorumu yaz.

KURALLAR
- Sadece verilen veriye dayan. Veride olmayan bir rakamı ASLA uydurma.
- Bir şeyi veriden çıkaramıyorsan "bu veriyle söylenemez" de; tahmin yürütme.
- Verinin başındaki «DÖNEM DURUMU» bloğuna MUTLAKA uy. Dönem devam ediyorsa yılı \
bitmiş gibi anlatma ve resmî kârı olduğu gibi doğru kabul etme.
- Birden çok yıl verildiyse («YILLAR ARASI KARŞILAŞTIRMA» bölümü) gidişatı mutlaka \
işle: satış büyüyor mu, marj daralıyor mu, borç ve stok birikiyor mu. Tek yılın \
fotoğrafıyla yetinme. Çok yıllı veride ŞUNLAR ZORUNLU: Özet'te en az bir cümle, «İyi \
Giden»de en az bir madde ve «Dikkat Edilmesi»nde en az bir madde yıllar arası gidişata \
ayrılsın — her birinde yılların rakamları yan yana yazılsın (2023: … / 2024: … / 2025: …).
- TÜRKİYE'DE ENFLASYON YÜKSEKTİR: yılları düz TL ile kıyaslamak YANILTICIDIR. "Satış %53 \
arttı" cümlesi, dolar bazında düşmüşken bile kurulabilir. Bu yüzden çok yıllı yorumda \
nominal TL artışını TEK BAŞINA olumlu sayma.
- «DÖVİZ BAZLI» bloğu varsa yıllar arası kıyası ÖNCE ona dayandır: "TL'de %53 arttı ama \
dolar bazında 1,0M USD'den 0,8M USD'ye, yani %20 düştü" gibi açıkça yaz. Stok, alacak ve \
borçta da aynısını yap — bu kalemlerde nominal büyüme çoğu zaman gerçek büyüme değil, \
sadece fiyat artışıdır.
- «ORANLAR VE DEVİR HIZLARI» bloğu asıl tahlildir; oranlar enflasyondan etkilenmez. \
Yorumda ŞU ÜÇÜNÜ mutlaka ele al: (1) STOK — devir hızı, bekleme günü ve stok/satış \
oranı yıllar içinde ne yönde gidiyor, stok şişiyor mu; (2) KREDİ BORÇLULUĞU — banka \
kredisi, kredi/aktif ve finansman gideri/satış yükü artıyor mu; (3) KÂRLILIK — brüt, \
faaliyet ve net marj ile ROE/ROA daralıyor mu. Her birinde yılların rakamlarını yan \
yana ver.
- Bir oran hücresi BOŞ ise o yıl için hesaplanamamıştır (payda sıfır ya da veri eksik). \
Boş hücreye "sıfır" muamelesi yapma; gerekiyorsa neden hesaplanamadığını söyle.
- Enflasyon oranı veride YOKTUR. Kendi bilginden bir TÜFE tahmini kullanacaksan kullandığın \
oranı rakamla yaz ve "kendi bilgimdeki TÜFE — veride yok" diye etiketle; veriden geliyormuş \
gibi sunma. Döviz bloğu yoksa da en azından nominal artışın enflasyonu içerdiğini söyle.
- Aynı büyüklük için iki farklı rakam varsa (ör. resmî gelir tablosu kârı ile fiili \
brüt marj) hangisine neden güvendiğini bir cümleyle söyle.
- Her iddiayı rakamla destekle. "Nakit sıkışık" değil, "kasada 722.411 TL var, aylık \
ortalama gideriniz 356.949 TL — yaklaşık 2 aylık" gibi.
- Terim kullanman gerekiyorsa hemen yanında bir cümleyle Türkçesini yaz.
- Abartma ve yumuşatma yapma. Kötü haber varsa açıkça yaz; iyi haber varsa hak ettiği \
kadar yaz.
- Rakamları Türkçe biçimde yaz (1.234.567,89 TL).

BİÇİM — tam olarak şu başlıkları kullan, başka başlık ekleme:

## Özet
En fazla 4 cümle. Şirketin bu yıl nasıl gittiğini bir sayfa okumak istemeyen birine anlat.

## İyi Giden 3 Şey
Madde madde, her maddede rakam olsun.

## Dikkat Edilmesi Gereken 3 Şey
En riskli olandan başla. Her maddede rakam ve neden riskli olduğu olsun.

## Karar Gerektiren 3 Konu
Şirket sahibinin karar vermesi gereken konular. Bu bir yapılacaklar listesi DEĞİLDİR: \
"şunu yapın" diye emir verme, "bu ay/bu hafta" gibi zaman biçme. Konuyu, rakamı ve \
karar verilmezse ne olacağını yaz. "X müşterisindeki 4,7M TL alacak toplam alacağın \
%41'i; tahsil edilemezse … Bu alacağın vadesi ve teminatı gözden geçirilmeli." gibi.

## Veride Göremediklerim
Yorumu sınırlayan eksikler. Yoksa "Önemli bir eksik görmedim." yaz.
"""


def yil_araligi(bas: str, bit: str, azami: int = AZAMI_YIL) -> tuple[list[int], int]:
    """
    Seçili tarih aralığının kapsadığı takvim yılları.

    Azami sınır aşılırsa EN YENİ yıllar tutulur (eski yıl fazlası düşer); dönen ikinci
    değer kaç yılın düştüğüdür — kullanıcıya uyarı göstermek için.
    """
    ilk = int((bas or bit or "")[:4] or 0)
    son = int((bit or bas or "")[:4] or 0)
    if not ilk or not son:
        return [], 0
    hepsi = list(range(min(ilk, son), max(ilk, son) + 1))
    return hepsi[-azami:], max(0, len(hepsi) - azami)


def ay_farki(bit: str, bugun: str) -> int:
    """Verinin bitişi ile bugün arasındaki tam ay sayısı (gelecek tarihte 0)."""
    try:
        son, simdi = date.fromisoformat(bit), date.fromisoformat(bugun)
    except ValueError:
        return 0
    ay = (simdi.year - son.year) * 12 + (simdi.month - son.month)
    if simdi.day < son.day:
        ay -= 1
    return max(0, ay)


@dataclass
class YilKapanis:
    """Bir yılın kapanış fotoğrafı — yıllar arası karşılaştırma için, ham kırılım yok."""

    yil: int
    tam: bool = True               # yıl tamamlandı mı (devam eden yıl kıyası bozar)
    net_satis: float = 0.0
    brut_kar: float = 0.0
    faaliyet_kari: float = 0.0
    net_kar: float = 0.0
    nakit: float = 0.0
    alacak: float = 0.0
    stok: float = 0.0
    kvyk: float = 0.0              # kısa vadeli yabancı kaynak
    uvyk: float = 0.0              # uzun vadeli yabancı kaynak
    donen: float = 0.0             # dönen varlıklar (cari oran için)
    ozkaynak: float = 0.0
    aktif_toplam: float = 0.0
    banka_kredisi: float = 0.0     # 300/303/400 — kredi borçluluğunun trendi
    smm: float = 0.0               # satışların maliyeti (62), işaretli (negatif)
    maliyet_eksik: bool = False    # 62 (SMM) girilmemiş → kâr şişik görünür
    faaliyet_gideri: float = 0.0   # 63, işaretli (gider → negatif)
    finansman_gideri: float = 0.0  # 66, işaretli (gider → negatif)
    satis_usd: float = 0.0         # Mikro'nun kendi kaydından, tarihî kurlarla
    kur_son: float = 0.0           # dönem sonu ima edilen TL/USD; 0 = güvenilir kur yok

    @property
    def doviz_var(self) -> bool:
        return self.kur_son > 0 and abs(self.satis_usd) > 0.005

    def usd(self, tl: float) -> float:
        """Dönem sonu bakiyesinin o günkü dolar karşılığı."""
        return tl / self.kur_son if self.kur_son > 0 else 0.0

    # Oranlar None dönebilir: payda sıfırsa uydurma 0,00 yazmak yerine hücre BOŞ kalır.
    # "Stok devir hızı 0" ile "hesaplanamıyor" farklı şeylerdir.
    @staticmethod
    def _bol(pay: float, payda: float, kat: float = 1.0) -> float | None:
        return (pay / payda * kat) if abs(payda) >= 0.005 else None

    def _marj(self, pay: float) -> float | None:
        return self._bol(pay, self.net_satis, 100.0)

    @property
    def brut_marj(self) -> float | None:
        return self._marj(self.brut_kar)

    @property
    def faaliyet_marj(self) -> float | None:
        return self._marj(self.faaliyet_kari)

    @property
    def net_marj(self) -> float | None:
        return self._marj(self.net_kar)

    @property
    def roe(self) -> float | None:
        """Özkaynak kârlılığı — özkaynak eksiyse anlamsızdır, o yüzden boş bırakılır."""
        return self._bol(self.net_kar, self.ozkaynak, 100.0) if self.ozkaynak > 0 else None

    @property
    def roa(self) -> float | None:
        return self._bol(self.net_kar, self.aktif_toplam, 100.0)

    @property
    def stok_devir(self) -> float | None:
        """Stok kaç kez döndü — SMM girilmemişse hesaplanamaz, uydurulmaz."""
        if self.maliyet_eksik or abs(self.smm) < 0.005:
            return None
        return self._bol(abs(self.smm), self.stok)

    @property
    def stok_gun(self) -> float | None:
        devir = self.stok_devir
        return (365.0 / devir) if devir and devir > 0 else None

    @property
    def stok_satis(self) -> float | None:
        """Stok / net satış — SMM olmasa da hesaplanır, stok şişkinliğinin kaba ölçüsü."""
        return self._bol(self.stok, self.net_satis, 100.0)

    @property
    def dso(self) -> float | None:
        """Alacak tahsil süresi (gün) — yıllar içinde uzuyorsa tahsilat bozuluyor."""
        return self._bol(self.alacak * 365.0, self.net_satis)

    @property
    def cari_oran(self) -> float | None:
        return self._bol(self.donen, self.kvyk)

    @property
    def asit_test(self) -> float | None:
        return self._bol(self.donen - self.stok, self.kvyk)

    @property
    def borc_ozkaynak(self) -> float | None:
        return self._bol(self.kvyk + self.uvyk, self.ozkaynak) if self.ozkaynak > 0 else None

    @property
    def kredi_aktif(self) -> float | None:
        return self._bol(self.banka_kredisi, self.aktif_toplam, 100.0)

    @property
    def finansman_yuku(self) -> float | None:
        """Faiz yükü: finansman gideri net satışın yüzde kaçını yiyor."""
        return self._bol(abs(self.finansman_gideri), self.net_satis, 100.0)


# Yıllar arası tabloda gösterilecek kalemler — az ve karşılaştırılabilir olanlar.
_YIL_KALEMLERI: tuple[tuple[str, str], ...] = (
    ("Net Satışlar", "net_satis"),
    ("Brüt Kâr", "brut_kar"),
    # Giderler trendin kalbi: satış büyürken gider daha hızlı büyüyor mu, faiz yükü
    # artıyor mu — bunlar olmadan "kâr düştü" cümlesinin sebebi görünmüyordu.
    ("Faaliyet Gideri (63)", "faaliyet_gideri"),
    ("Finansman Gideri (66)", "finansman_gideri"),
    ("Faaliyet Kârı", "faaliyet_kari"),
    ("Dönem Net Kârı", "net_kar"),
    ("Nakit (dönem sonu)", "nakit"),
    ("Ticari Alacak (dönem sonu)", "alacak"),
    ("Stok (dönem sonu)", "stok"),
    ("Kısa Vadeli Borç (dönem sonu)", "kvyk"),
    ("Uzun Vadeli Borç (dönem sonu)", "uvyk"),
    ("Banka Kredisi (dönem sonu)", "banka_kredisi"),
    ("Özkaynak (dönem sonu)", "ozkaynak"),
    ("Aktif Toplam (dönem sonu)", "aktif_toplam"),
)

# Asıl tahlil burada: seviyeler değil ORANLAR yıllar arası kıyaslanabilir. Nominal TL
# enflasyonla şişer, oran şişmez — "stok 5 yıldır aynı" ile "stok 90 gün bekliyor"
# arasındaki fark budur. Kullanıcının özellikle istediği kalemler: stok, kredi
# borçluluğu ve kârlılık.
_ORAN_SATIRLARI: tuple[tuple[str, str], ...] = (
    ("Brüt Marj (%)", "brut_marj"),
    ("Faaliyet Marjı (%)", "faaliyet_marj"),
    ("Net Marj (%)", "net_marj"),
    ("Özkaynak Kârlılığı — ROE (%)", "roe"),
    ("Aktif Kârlılığı — ROA (%)", "roa"),
    ("Stok Devir Hızı (kez/yıl)", "stok_devir"),
    ("Stok Bekleme Süresi (gün)", "stok_gun"),
    ("Stok / Net Satış (%)", "stok_satis"),
    ("Alacak Tahsil Süresi — DSO (gün)", "dso"),
    ("Cari Oran (x)", "cari_oran"),
    ("Asit-Test (x)", "asit_test"),
    ("Borç / Özkaynak (x)", "borc_ozkaynak"),
    ("Banka Kredisi / Aktif (%)", "kredi_aktif"),
    ("Finansman Gideri / Net Satış (%)", "finansman_yuku"),
)

# Dolar karşılığı verilecek bilanço kalemleri — stok, alacak ve borçta nominal TL
# kıyası en çok burada yanıltır (kullanıcının işaret ettiği yer).
_DOVIZ_KALEMLERI: tuple[tuple[str, str], ...] = (
    ("Ticari Alacak", "alacak"),
    ("Stok", "stok"),
    ("Kısa Vadeli Borç", "kvyk"),
    ("Nakit", "nakit"),
    ("Özkaynak", "ozkaynak"),
)


@dataclass
class TabloSatir:
    """Tablonun bir satırı — hücreler yıl sırasına göre, boş hücre 'hesaplanamadı'."""

    etiket: str
    hucreler: list[str] = field(default_factory=list)
    degisim: str = ""
    iyi: bool | None = None    # değişim lehte mi (renk için); None = nötr


@dataclass
class TabloBolum:
    baslik: str
    satirlar: list[TabloSatir] = field(default_factory=list)


def _kisa(v: float) -> str:
    """Tabloya sığan kısa tutar: 41,2M · 357B · 1.234. 6 yıl yan yana ancak böyle sığar."""
    m = abs(v)
    if m >= 1_000_000:
        return f"{v / 1_000_000:.1f}M".replace(".", ",")
    if m >= 1_000:
        return f"{v / 1_000:.0f}B"
    return f"{v:,.0f}".replace(",", ".")


def _oran_metni(v: float | None, birim: str) -> str:
    if v is None:
        return "—"
    if birim in ("TL", "USD"):
        return _kisa(v)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# (etiket, alan, birim, artis_iyi) — artis_iyi None ise değişim renklendirilmez.
_TL_SATIR = (
    ("Net Satışlar", "net_satis", True), ("Brüt Kâr", "brut_kar", True),
    ("Faaliyet Kârı", "faaliyet_kari", True), ("Dönem Net Kârı", "net_kar", True),
    ("Nakit", "nakit", True), ("Ticari Alacak", "alacak", False),
    ("Stok", "stok", False), ("Kısa Vadeli Borç", "kvyk", False),
    ("Uzun Vadeli Borç", "uvyk", False), ("Banka Kredisi", "banka_kredisi", False),
    ("Özkaynak", "ozkaynak", True), ("Aktif Toplam", "aktif_toplam", None),
)
_USD_SATIR = (
    ("Ticari Alacak", "alacak", False), ("Stok", "stok", False),
    ("Kısa Vadeli Borç", "kvyk", False), ("Banka Kredisi", "banka_kredisi", False),
    ("Nakit", "nakit", True), ("Özkaynak", "ozkaynak", True),
)
_ORAN_SATIR = (
    ("Brüt Marj", "brut_marj", "%", True), ("Faaliyet Marjı", "faaliyet_marj", "%", True),
    ("Net Marj", "net_marj", "%", True), ("Özkaynak Kârlılığı (ROE)", "roe", "%", True),
    ("Aktif Kârlılığı (ROA)", "roa", "%", True),
    ("Stok Devir Hızı", "stok_devir", "kez/yıl", True),
    ("Stok Bekleme Süresi", "stok_gun", "gün", False),
    ("Stok / Net Satış", "stok_satis", "%", False),
    ("Alacak Tahsil Süresi (DSO)", "dso", "gün", False),
    ("Cari Oran", "cari_oran", "x", True), ("Asit-Test", "asit_test", "x", True),
    ("Borç / Özkaynak", "borc_ozkaynak", "x", False),
    ("Banka Kredisi / Aktif", "kredi_aktif", "%", False),
    ("Finansman Gideri / Net Satış", "finansman_yuku", "%", False),
)


def _degisim(ilk: float | None, son: float | None, birim: str,
             artis_iyi: bool | None) -> tuple[str, bool | None]:
    """
    İlk yıldan son yıla değişim.

    Tutarlarda YÜZDE, oranlarda PUAN farkı verilir — "cari oran %-33 düştü" demek
    yanıltıcıdır, "−0,46 puan" doğrudur. Uçlar hesaplanamıyorsa değişim de yazılmaz.
    """
    if ilk is None or son is None:
        return "—", None
    if birim in ("TL", "USD"):
        if abs(ilk) < 0.005:
            return "—", None
        yuzde_v = (son - ilk) / abs(ilk) * 100
        metin = f"%{yuzde_v:+,.0f}".replace(",", ".")
    else:
        fark = son - ilk
        metin = f"{fark:+,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        metin += " puan" if birim == "%" else ""
    artti = son > ilk
    iyi = None if artis_iyi is None or abs(son - ilk) < 1e-9 else (artti == artis_iyi)
    return metin, iyi


def yillar_tablosu(kapanislar: list[YilKapanis]) -> tuple[list[int], list[TabloBolum]]:
    """
    Yıllar arası karşılaştırmayı DETERMİNİSTİK olarak kurar.

    Modele bırakıldığında hangi satırı anacağını kendi seçiyordu; kullanıcı her seferinde
    tam mukayese istiyor. Burada hesap bizde: her yıl, her kalem, her oran ve ilk→son
    değişim her zaman tam çıkar. Model bu tabloyu yorumlar, üretmez.
    """
    if len(kapanislar) < 2:
        return [], []
    s = sorted(kapanislar, key=lambda k: k.yil)
    yillar = [k.yil for k in s]

    def bolum(baslik: str, tarif, deger, birim: str) -> TabloBolum:
        satirlar = []
        for etiket, alan, artis_iyi in tarif:
            degerler = [deger(k, alan) for k in s]
            metin, iyi = _degisim(degerler[0], degerler[-1], birim, artis_iyi)
            satirlar.append(TabloSatir(
                etiket, [_oran_metni(d, birim) for d in degerler], metin, iyi))
        return TabloBolum(baslik, satirlar)

    bolumler = [bolum("TUTARLAR (TL)", _TL_SATIR,
                      lambda k, a: getattr(k, a), "TL")]

    if all(k.doviz_var for k in s):
        usd = TabloBolum("DOLAR BAZINDA (Mikro'nun kendi kur kaydından)")
        kurlar = [k.kur_son for k in s]
        usd.satirlar.append(TabloSatir(
            "TL/USD kuru (dönem sonu)", [_oran_metni(k, "x") for k in kurlar],
            *_degisim(kurlar[0], kurlar[-1], "x", None)))
        satislar = [k.satis_usd for k in s]
        usd.satirlar.append(TabloSatir(
            "Net Satışlar", [_oran_metni(v, "USD") for v in satislar],
            *_degisim(satislar[0], satislar[-1], "USD", True)))
        usd.satirlar += bolum("", _USD_SATIR,
                              lambda k, a: k.usd(getattr(k, a)), "USD").satirlar
        bolumler.append(usd)

    bolumler.append(TabloBolum("ORANLAR VE DEVİR HIZLARI", [
        TabloSatir(etiket + (f" ({birim})" if birim not in ("%", "x") else
                             ("" if birim == "x" else " (%)")),
                   [_oran_metni(getattr(k, alan), birim) for k in s],
                   *_degisim(getattr(s[0], alan), getattr(s[-1], alan), birim, artis_iyi))
        for etiket, alan, birim, artis_iyi in _ORAN_SATIR
    ]))
    return yillar, bolumler


def yillar_arasi_csv(kapanislar: list[YilKapanis]) -> str:
    """Yılları yan yana koyan karşılaştırma tablosu — trendi tek bakışta görünür kılar."""
    if len(kapanislar) < 2:
        return ""
    sirali = sorted(kapanislar, key=lambda k: k.yil)

    def satir(etiket: str, deger) -> str:
        """Bir kalem satırı; hesaplanamayan hücre BOŞ kalır (uydurma 0,00 yazılmaz)."""
        return etiket + ";" + ";".join(
            "" if (d := deger(k)) is None else csv_sayi(d) for k in sirali)

    out = ["Kalem;" + ";".join(str(k.yil) for k in sirali)]
    out += [satir(e, lambda k, a=a: getattr(k, a)) for e, a in _YIL_KALEMLERI]

    out.append("")
    out.append("--- ORANLAR VE DEVİR HIZLARI (yıllar arası asıl kıyas) ---")
    out += [satir(e, lambda k, a=a: getattr(k, a)) for e, a in _ORAN_SATIRLARI]

    # DÖVİZ BLOĞU: nominal TL kıyası yüksek enflasyonda hiçbir şey anlatmaz — 3 yılda
    # "satış %53 arttı" demek, dolar bazında düşmüşken bile mümkündür. Kur Mikro'nun
    # kendi kaydından ima edilir; güvenilir kur yoksa blok HİÇ yazılmaz.
    if all(k.doviz_var for k in sirali):
        out.append("")
        out.append("--- DÖVİZ BAZLI (Mikro'nun kendi kur kaydından) ---")
        out.append(satir("TL/USD kuru (dönem sonu)", lambda k: k.kur_son))
        out.append(satir("Net Satışlar (USD)", lambda k: k.satis_usd))
        out += [satir(f"{e} (USD)", lambda k, a=a: k.usd(getattr(k, a)))
                for e, a in _DOVIZ_KALEMLERI]

    # Kıyası bozan yıllar açıkça işaretlenir; model "satış düştü" diye yanlış okumasın.
    notlar = []
    for k in sirali:
        if not k.tam:
            notlar.append(f"NOT;{k.yil} yılı TAMAMLANMADI — rakamlar yılın tamamını "
                          "kapsamaz, önceki yıllarla doğrudan kıyaslanamaz.")
        if k.maliyet_eksik:
            notlar.append(f"NOT;{k.yil} yılında satışların maliyeti (62) girilmemiş — "
                          "brüt ve net kâr olduğundan yüksek görünüyor.")
    if notlar:
        out.append("")
        out.extend(notlar)
    return "\r\n".join(out)


@dataclass
class AiVeriPaketi:
    """Modele gönderilecek ham rapor verisi — bölüm bölüm."""

    yil: int = 0
    bas: str = ""
    bit: str = ""
    firma: str = ""
    bolumler: list[tuple[str, str]] = field(default_factory=list)
    # Dönem bağlamı — modelin "yılı kapattı" gibi yanlış çıkarım yapmasını engeller.
    bugun: str = ""
    tamamlandi: bool = False       # dönem sonu geçti mi (yıl bitti mi)
    ay_sayisi: int = 0             # veride fiilen kaç ay var
    gecikme_ay: int = 0            # verinin bitişi ile bugün arasındaki ay farkı
    calisma_yili: int = 0          # Mikro'da seçili çalışma yılı (veritabanı yılı)
    yillar: list[int] = field(default_factory=list)   # çok yıllı analizde kapsanan yıllar
    kapanislar: list = field(default_factory=list)   # deterministik mukayese tablosu için

    @property
    def aralik_bas(self) -> str:
        """Verinin gerçek başlangıcı: çok yıllıda en eski yılın 1 Ocak'ı."""
        return f"{self.yillar[0]}-01-01" if len(self.yillar) > 1 else self.bas

    @property
    def aralik(self) -> str:
        return f"{self.aralik_bas} – {self.bit}"

    @property
    def kapsam_notu(self) -> str:
        """
        Çok yıllı pakette hangi bölümün hangi yıla ait olduğunu söyler.

        Bu blok olmadan model, özet tablodaki geçmiş yılları ham bölümlerle karıştırıp
        "2023'te şu müşteriden alacak vardı" gibi veride olmayan çıkarımlar yapar.
        """
        if len(self.yillar) < 2:
            return ""
        ilk, son = self.yillar[0], self.yillar[-1]
        return "\n".join([
            f"ÇOK YILLI ANALİZ: Veri {ilk}–{son} yıllarını kapsar ({len(self.yillar)} yıl).",
            f"«YILLAR ARASI KARŞILAŞTIRMA» bölümü bu yılların kapanış rakamlarını yan yana "
            f"verir. DİĞER TÜM BÖLÜMLER YALNIZ {son} yılına aittir — geçmiş yıllar için "
            "cari, fatura veya nakit akışı kırılımı YOKTUR, sorulursa \"veride yok\" de.",
            "Tutarlar NOMİNAL TL'dir, enflasyona göre düzeltilmemiştir. Yıllar arası artışı "
            "yorumlarken bunu bir cümleyle belirt; enflasyon oranı uydurma.",
        ])

    @property
    def _bayatlik_notu(self) -> list[str]:
        """
        Veri bugüne göre eskiyse modeli bugüne çeker.

        Kullanıcı 2023–2025 aralığını 2026 temmuzda yorumlattığında model 2025 Aralık'ta
        yaşıyormuş gibi «bu ay şunu yapın» yazıyordu — aradan 7 ay geçmişti (canlıda görüldü).

        Boşluğun SEBEBİ de söylenir: Mikro her çalışma yılını ayrı veritabanında tutar, yani
        sonraki aylar "kaydedilmemiş" değil, başka veritabanındadır. Bu söylenmeyince model
        "kayıtlarınız eksik, bir hafta içinde sisteme işleyin, kör uçmayın" gibi yanlış
        tavsiye veriyordu (canlıda görüldü).
        """
        if self.gecikme_ay < 2:
            return []
        sebep = (
            f"Bu veri Mikro'nun {self.calisma_yili} ÇALIŞMA YILI veritabanından geldi. "
            if self.calisma_yili else "Bu veri seçilen dönemin veritabanından geldi. "
        )
        return [
            f"DİKKAT — VERİ GÜNCEL DEĞİL: Bugün {self.bugun}, elindeki en yeni kayıt "
            f"{self.bit} tarihli. Arada yaklaşık {self.gecikme_ay} ay var ve bu aylara ait "
            "HİÇBİR hareket veride yok.",
            "BU BİR KAYIT EKSİKLİĞİ DEĞİLDİR. " + sebep + "Mikro her çalışma yılını ayrı "
            "veritabanında tutar; sonraki aylara ait hareketler kaydedilmemiş değil, başka "
            "bir veritabanındadır ve bu pakete girmemiştir.",
            "Bu yüzden «kayıtlarınızı acilen işleyin», «verileriniz eksik», «kör uçuyorsunuz» "
            "gibi tavsiyeler YAZMA — yanlış olur. Bunu yalnız «Veride Göremediklerim» "
            "bölümünde bir madde olarak belirt; «Karar Gerektiren 3 Konu»dan yer harcama.",
            f"«şu an», «bugün itibarıyla», «bu ay» deme; «{self.bit} itibarıyla» de. "
            "Bakiyeler, alacaklar ve nakit bugün farklı olabilir.",
        ]

    @property
    def donem_notu(self) -> str:
        """
        Modele dönemin durumunu AÇIKÇA söyler.

        Bu blok olmadan model, 1 Ocak–31 Aralık aralığını görüp yılın bittiğini sanıyor
        ("2026'yı 19,5M ile kapattı") ve yıl sonu kapanışı yapılmadığı için şişik görünen
        resmî kârı gerçek sanıyordu — canlıda ikisi de görüldü.
        """
        satirlar = [f"BUGÜNÜN TARİHİ: {self.bugun or '(bilinmiyor)'}"]
        if self.tamamlandi:
            satirlar += [
                f"DÖNEM DURUMU: {self.yil} yılı TAMAMLANDI. Veri tam yılı kapsıyor.",
            ]
            satirlar += self._bayatlik_notu
        else:
            satirlar += [
                f"DÖNEM DURUMU: {self.yil} yılı HENÜZ BİTMEDİ — yıl devam ediyor.",
                f"Aşağıdaki veri {self.bas} – {self.bit} arasını, yani yılın ilk "
                f"{self.ay_sayisi or '?'} ayını kapsar. Kalan aylara ait hiçbir veri yoktur.",
                f"Bu yüzden «yılı kapattı», «yıl sonunda», «{self.yil} yılını … ile "
                f"tamamladı» gibi ifadeler KULLANMA. «Yılın ilk {self.ay_sayisi or '?'} "
                "ayında» diye yaz.",
                "Yıllık toplam çıkarımı yapma; yapacaksan «yıllıklandırılmış tahmin» diye "
                "açıkça etiketle.",
                "YIL SONU KAPANIŞI HENÜZ YAPILMADI: satışların maliyeti (62x), amortisman "
                "ve karşılık kayıtları genelde dönem sonunda işlenir. Bu yüzden RESMÎ gelir "
                "tablosundaki brüt/net kâr GERÇEKTEN OLDUĞUNDAN YÜKSEK görünür. Kârlılık "
                "yorumunu «NAKİT VE KÂRLILIK» bölümündeki fiili brüt marja dayandır ve bu "
                "farkı okuyucuya bir cümleyle açıkla.",
            ]
        return "\n".join(satirlar)

    @property
    def metin(self) -> str:
        """Bölümleri tek belgeye çevirir (modele giden gövde)."""
        parcalar = [
            f"FİRMA: {self.firma or '(belirtilmemiş)'}",
            f"VERİ ARALIĞI: {self.aralik}",
            "",
        ]
        if self.kapsam_notu:
            parcalar += [self.kapsam_notu, ""]
        parcalar += [self.donem_notu, ""]
        for baslik, icerik in self.bolumler:
            parcalar.append(f"### {baslik}")
            parcalar.append(icerik.strip())
            parcalar.append("")
        return "\n".join(parcalar).strip()

    @property
    def karakter_sayisi(self) -> int:
        return len(self.metin)

    @property
    def satir_sayisi(self) -> int:
        return sum(icerik.count("\n") + 1 for _, icerik in self.bolumler)

    def ozet_satiri(self) -> str:
        """Kullanıcıya «ne gönderildi» şeffaflığı için tek satır."""
        adlar = ", ".join(b for b, _ in self.bolumler) or "—"
        return (f"{len(self.bolumler)} bölüm · {self.satir_sayisi} satır · "
                f"{self.karakter_sayisi:,} karakter".replace(",", ".") + f" · {adlar}")


@dataclass
class AiYorum:
    """Modelden dönen yorum ve üretim bilgileri."""

    metin: str = ""
    model: str = ""
    yil: int = 0
    bas: str = ""
    bit: str = ""
    firma: str = ""
    girdi_token: int = 0
    cikti_token: int = 0
    veri_ozeti: str = ""
    saglayici: str = ""
    kapsam_bas: str = ""   # çok yıllıda en eski yılın başı; boşsa bas ile aynı
    # Yıllar arası mukayese tablosu buradan kurulur — model çıktısından BAĞIMSIZ.
    kapanislar: list = field(default_factory=list)

    @property
    def aralik_bas(self) -> str:
        return self.kapsam_bas or self.bas

    @property
    def aralik(self) -> str:
        return f"{self.aralik_bas} – {self.bit}"

    @property
    def bos(self) -> bool:
        return not self.metin.strip()

    @property
    def toplam_token(self) -> int:
        return self.girdi_token + self.cikti_token


def build_ai_veri_paketi(
    *,
    yil: int,
    bas: str,
    bit: str,
    firma: str = "",
    bolumler: list[tuple[str, str]] | None = None,
    bugun: str = "",
    tamamlandi: bool = False,
    ay_sayisi: int = 0,
    gecikme_ay: int = 0,
    calisma_yili: int = 0,
    yillar: list[int] | None = None,
    kapanislar: list | None = None,
) -> AiVeriPaketi:
    """Rapor CSV'lerinden veri paketini kurar; boş/hatalı bölümler elenir."""
    temiz: list[tuple[str, str]] = []
    for baslik, icerik in bolumler or []:
        if icerik and icerik.strip():
            temiz.append((baslik, icerik))
    return AiVeriPaketi(
        yil=yil, bas=bas, bit=bit, firma=firma, bolumler=temiz,
        bugun=bugun, tamamlandi=tamamlandi, ay_sayisi=ay_sayisi,
        gecikme_ay=gecikme_ay, calisma_yili=calisma_yili,
        yillar=sorted(yillar or []), kapanislar=list(kapanislar or []))


def ai_yorum_csv(y: AiYorum) -> str:
    """Yorumu Türkçe Excel uyumlu CSV'ye çevirir (satır satır metin)."""
    out = ["Bölüm;İçerik"]
    out.append(f"DÖNEM;{y.aralik}")
    out.append(f"SAĞLAYICI;{y.saglayici}")
    out.append(f"MODEL;{y.model}")
    out.append(f"TOKEN;girdi {csv_sayi(y.girdi_token)} / çıktı {csv_sayi(y.cikti_token)}")

    # Deterministik mukayese CSV'ye de girer — Excel'de kendi grafiğini çizebilsin.
    yillar, bolumler = yillar_tablosu(y.kapanislar)
    if yillar:
        out.append("")
        out.append("MUKAYESE;Kalem;" + ";".join(str(v) for v in yillar)
                   + f";{yillar[0]}→{yillar[-1]}")
        for bolum in bolumler:
            if bolum.baslik:
                out.append(f"MUKAYESE;{bolum.baslik}")
            for satir in bolum.satirlar:
                out.append("MUKAYESE;" + ";".join(
                    [satir.etiket.replace(";", ","), *satir.hucreler, satir.degisim]))
        out.append("")

    for satir in y.metin.splitlines():
        temiz = satir.replace(";", ",").strip()
        if temiz:
            out.append(f"YORUM;{temiz}")
    return "\r\n".join(out)
