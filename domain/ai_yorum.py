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


# Maliyet kapanışı (62) yapılmamışsa bu kalemler şişer — kıyasa girmemeli.
# Satış, bakiye ve likidite kalemleri etkilenmez; onlar SMM'den bağımsızdır.
# Satışın maliyeti (62) işlenmemiş bir yılda bu kalemler GERÇEK DEĞİLDİR.
#
# Eksik olan «621 SMM / 153 Ticari Mallar» fişinin İKİ ayağı var, o yüzden hata da
# iki yerde: 621 borçlanmadığı için KÂR şişer, 153 alacaklanmadığı için STOK şişer —
# tam olarak aynı tutarda. Önce yalnız kâr ayağını eliyorduk; canlıda 2026 stoğu
# 21,5 milyon TL (459 bin USD) görünüp «geçen yıla göre %52 arttı» diyordu. İşlenmemiş
# ~13,4 milyonluk maliyet düşülünce gerçek stok ~8,1 milyon TL (174 bin USD), yani
# %42 AZALMIŞ çıkıyordu. Yön bile tersti; kullanıcı «biz stoğa mal almıyoruz, bu artış
# imkânsız» derken haklıydı. Stok şiştiği için ondan türeyen her oran da yanlıştı
# (Stok/Net Satış %109,8 → gerçekte %40; Cari Oran 2,25 → 1,28).
#
# Asit-Test listede YOK: (dönen − stok) şişkinliği zaten götürür, o oran temiz kalır.
_KAPANISA_BAGLI = frozenset({
    # kâr ayağı
    "brut_kar", "faaliyet_kari", "net_kar",
    "brut_marj", "faaliyet_marj", "net_marj", "roe", "roa",
    # stok ayağı — ve şişmiş stoktan/özkaynaktan türeyen oranlar
    "stok", "ozkaynak", "aktif_toplam",
    "stok_satis", "cari_oran", "borc_ozkaynak", "kredi_aktif",
})


@dataclass
class YilKapanis:
    """Bir yılın kapanış fotoğrafı — yıllar arası karşılaştırma için, ham kırılım yok."""

    yil: int
    # SEÇİLEN TARİH ARALIĞI KUTSAL. Sütun, o yılın seçili aralıkla KESİŞİMİDİR:
    # 28.07.2025–28.07.2026 seçiliyken 2025 sütunu 28.07–31.12, 2026 sütunu 01.01–28.07.
    # Eskiden her yıl 1 Ocak'tan okunuyordu; kullanıcı «seçtiğim aralığın bir gün öncesi
    # bile bu tabloda olmamalı» diyerek bunu reddetti — haklıydı, seçim onun.
    bas: str = ""                  # okunan pencerenin başlangıcı
    bit: str = ""                  # okunan pencerenin bitişi
    tam: bool = True               # pencere yılın tamamını kapsıyor mu
    net_satis: float = 0.0
    brut_kar: float = 0.0
    faaliyet_kari: float = 0.0
    net_kar: float = 0.0
    # Alacak/borç/nakit CARİ ve GL HAREKET kaynaklarından gelir — ilgili sekmelerin
    # gösterdiği canlı rakamlarla aynı. Mizanın 120/320 bakiyeleri kullanılmaz: bu
    # şirkette bilanço hesapları işlenmediği için beş yıl boyunca sabit çıkıyordu,
    # oysa Alacak & Borç sekmesi her yıl farklı gösteriyordu (canlıda görüldü).
    nakit: float = 0.0             # 100/101/102/108 GL bakiyesi (Nakit Akış sekmesi)
    alacak: float = 0.0            # müşteri açık bakiyesi (Alacak & Borç sekmesi)
    borc: float = 0.0              # satıcı açık bakiyesi (Alacak & Borç sekmesi)
    alacak_gecikmis: float = 0.0   # vadesi geçmiş müşteri alacağı
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
    kur_ort: float = 0.0           # dönem ortalama kuru — AKIŞ kalemleri için

    # CANLI (STOK HAREKETİ) AYAK — muhasebeden BAĞIMSIZ.
    #
    # Kullanıcının kuralı: ilk iki sekme (Bilanço, Gelir Tablosu) resmi kayda dayanır,
    # DİĞER HEPSİ canlı/reel veriye. Mukayese tablosunu mizan + GL gelir tablosundan
    # kurmak bu yüzden yanlıştı: satışın maliyeti (62) işlenmemiş bir yılda kâr
    # satırlarının hepsi «—» kalıyordu, oysa Nakit & Kârlılık sekmesi aynı dönemin
    # kârlılığını depodan geçen maldan zaten hesaplıyordu. Kullanıcı haklı olarak
    # «bu rakamları bulabiliyorsun, tabloda neden yok?» dedi.
    #
    # Bu üç alan 62'ye HİÇ dokunmaz; muhasebeci kapanış yapmasa da doludur.
    fiili_satis: float = 0.0       # depodan çıkan mal (irsaliye + fatura)
    fiili_alis: float = 0.0        # depoya giren mal (fatura)
    fiili_var: bool = False        # stok hareketi okunabildi mi

    @property
    def fiili_fark(self) -> float | None:
        """Fiili al-sat farkı: satılan malın maliyeti DEĞİL, alınan malın tamamıyla."""
        return (self.fiili_satis - self.fiili_alis) if self.fiili_var else None

    @property
    def fiili_marj(self) -> float | None:
        f = self.fiili_fark
        return self._bol(f, self.fiili_satis, 100.0) if f is not None else None

    # EKSİK OLAN YALNIZ 62. Faaliyet gideri (63) ve finansman gideri (66) normal
    # işlenir; maliyet kapanışı onları hiç ilgilendirmez. O yüzden brüt ayağı canlı
    # veriden koyunca aşağısı da kurulur — «hesaplanamaz» demek fazla kesindi.
    # Bu, Nakit & Kârlılık'taki RESMİ → FİİLİ köprüsünün aynısıdır.
    @property
    def fiili_faaliyet_kari(self) -> float | None:
        f = self.fiili_fark
        return None if f is None else f + self.faaliyet_gideri      # 63 işaretli negatif

    @property
    def fiili_net_kar(self) -> float | None:
        """Vergi ÖNCESİ: 691/692 her kurulumda ara dönemde işlenmiyor, uydurmuyoruz."""
        f = self.fiili_faaliyet_kari
        return None if f is None else f + self.finansman_gideri     # 66 işaretli negatif

    @property
    def fiili_faaliyet_marj(self) -> float | None:
        f = self.fiili_faaliyet_kari
        return self._bol(f, self.fiili_satis, 100.0) if f is not None else None

    @property
    def fiili_net_marj(self) -> float | None:
        f = self.fiili_net_kar
        return self._bol(f, self.fiili_satis, 100.0) if f is not None else None

    def pencere(self) -> str:
        """«28.07–31.12» — sütunun gerçekte hangi günleri kapsadığı. Tam yılda boş."""
        if self.tam or len(self.bas) != 10 or len(self.bit) != 10:
            return ""
        return f"{self.bas[8:10]}.{self.bas[5:7]}–{self.bit[8:10]}.{self.bit[5:7]}"

    def basligi(self) -> str:
        """
        Sütun başlığı: «2025», «2025 (28.07–31.12)» ya da «28.07.2024–28.07.2025».

        Dönem iki takvim yılına yayılıyorsa (geçen yılın aynı dönemi sütunu) yıl tek
        başına yanıltır — o yüzden başlıkta iki tarih de yılıyla birlikte yazılır.
        """
        if len(self.bas) == 10 and len(self.bit) == 10 and self.bas[:4] != self.bit[:4]:
            return (f"{self.bas[8:10]}.{self.bas[5:7]}.{self.bas[:4]}–"
                    f"{self.bit[8:10]}.{self.bit[5:7]}.{self.bit[:4]}")
        p = self.pencere()
        return f"{self.yil} ({p})" if p else str(self.yil)

    @property
    def dolu(self) -> bool:
        """
        Bu yıl veritabanında gerçekten var mı?

        Mikro her çalışma yılını ayrı veritabanında tutabilir; olmayan yılın sorgusu
        hata değil BOŞ döner. Sıfır satırı tabloya girerse model "satış sıfırdan 41M'ye
        çıkmış" diye okur — o yüzden böyle yıllar hiç eklenmez.
        """
        return (abs(self.net_satis) > 0.005 or abs(self.aktif_toplam) > 0.005
                or abs(self.alacak) > 0.005)

    @property
    def doviz_var(self) -> bool:
        return self.kur_son > 0 and abs(self.satis_usd) > 0.005

    def usd(self, tl: float | None) -> float | None:
        """BAKİYE kaleminin dönem sonundaki dolar karşılığı; hesaplanamazsa None."""
        if tl is None or self.kur_son <= 0:
            return None
        return tl / self.kur_son

    def usd_akis(self, tl: float | None) -> float | None:
        """
        AKIŞ kaleminin (satış, kâr, gider) dolar karşılığı — dönem ORTALAMA kuruyla.

        Yıl boyunca oluşan bir tutarı yıl sonu kuruyla çevirmek yanlış olur: kur yıl
        içinde yükseldiyse tüm ciroyu en pahalı günün kuruyla bölmüş oluruz.
        """
        kur = self.kur_ort or self.kur_son
        if tl is None or kur <= 0:
            return None
        return tl / kur

    def kalem(self, ad: str) -> float | None:
        """
        Bir kalemin karşılaştırmaya girecek değeri; hesaplanamıyorsa None.

        Maliyet kapanışı yapılmamış bir yılda (62 boş) kâr kalemleri GERÇEKTE
        OLDUĞUNDAN yüksektir. Canlıda süren yılın brüt marjı %100 çıkıyor, tablo da
        bunu «brüt kâr %434 arttı» diye yeşille kutluyordu — oysa satışlar %32
        düşmüştü. Şişik rakamı kıyaslamaktansa hiç göstermemek doğru.
        """
        if self.maliyet_eksik and ad in _KAPANISA_BAGLI:
            return None
        return getattr(self, ad)

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
    def gecikme_orani(self) -> float | None:
        """Alacağın yüzde kaçı vadesini geçmiş — tahsilat kalitesinin doğrudan ölçüsü."""
        return self._bol(self.alacak_gecikmis, self.alacak, 100.0) if self.alacak > 0 else None

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
    hucreler: list[str] = field(default_factory=list)   # ekrana yazılan kısa biçim
    degerler: list[float | None] = field(default_factory=list)   # ham — CSV/Excel için
    degisim: str = ""
    iyi: bool | None = None       # değişim lehte mi (renk için); None = nötr
    eksi: list[bool] = field(default_factory=list)   # hangi hücre negatif (kırmızı)
    sabit: bool = False           # kıyas değeri yok → tabloya alınmaz


@dataclass
class TabloBolum:
    baslik: str
    satirlar: list[TabloSatir] = field(default_factory=list)


def _kisa(v: float) -> str:
    """
    Tabloya sığan tutar — birim AÇIK YAZILIR, milyon altı TAM gösterilir.

    İki ders:
    • «41,2M / 650B» kısaltması Türkçede yanlış okunuyordu (B → milyar). Kelime yazılır.
    • «bin» kısaltması fazla yuvarlıyordu: 176.270 ile 176.100 ikisi de «176 bin» çıkıp
      farklı yılları aynı gösteriyordu (canlıda kullanıcı fark etti). Artık milyonun
      altı tam yazılır; yuvarlama yalnız gerçekten uzun sayılarda devreye girer.
    """
    m = abs(v)
    if m >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f} milyar".replace(".", ",")
    if m >= 1_000_000:
        return f"{v / 1_000_000:.1f} milyon".replace(".", ",")
    return f"{v:,.0f}".replace(",", ".")


def _oran_metni(v: float | None, birim: str) -> str:
    if v is None:
        return "—"
    if birim in ("TL", "USD"):
        return _kisa(v)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# TL BÖLÜMÜ YOKTUR. Yüksek enflasyonda nominal TL kıyası hiçbir şey anlatmaz: her
# kalem her yıl "artmış" görünür. Tablo yalnız DOLAR ve ORAN bölümlerinden oluşur —
# ikisi de enflasyondan arınmıştır.

# (etiket, alan, artis_iyi) — AKIŞ kalemleri: dönem ortalama kuruyla çevrilir.
_USD_AKIS = (
    ("Brüt Kâr", "brut_kar", True),
    ("Faaliyet Kârı", "faaliyet_kari", True),
    ("Dönem Net Kârı", "net_kar", True),
)
# CANLI AYAK — depodan geçen mal. 62'ye bağlı değil, muhasebe kapanışı beklemez;
# maliyet işlenmemiş yılda ÜSTTEKİ satırlar «—» olsa da bunlar dolu kalır.
_USD_FIILI = (
    ("Fiili Satış (depodan çıkan)", "fiili_satis", True),
    ("Fiili Alış (depoya giren)", "fiili_alis", None),
    ("Fiili Al-Sat Farkı", "fiili_fark", True),
    ("Fiili Faaliyet Kârı", "fiili_faaliyet_kari", True),
    ("Fiili Net Kâr (vergi öncesi)", "fiili_net_kar", True),
)
# BAKİYE kalemleri: dönem sonu kuruyla çevrilir.
_USD_BAKIYE = (
    ("Ticari Alacak", "alacak", False),
    ("  · vadesi geçmiş", "alacak_gecikmis", False),
    ("Ticari Borç (satıcı)", "borc", False),
    ("Stok", "stok", False),
    ("Kısa Vadeli Borç", "kvyk", False),
    ("Uzun Vadeli Borç", "uvyk", False),
    ("Banka Kredisi", "banka_kredisi", False),
    ("Nakit", "nakit", True),
    ("Özkaynak", "ozkaynak", True),
    ("Aktif Toplam", "aktif_toplam", None),
)
_ORAN_SATIR = (
    # Canlı ayak — 62'siz de hesaplanır (eksik olan yalnız 62; 63 ve 66 işlenmiş).
    ("Fiili Al-Sat Marjı", "fiili_marj", "%", True),
    ("Fiili Faaliyet Marjı", "fiili_faaliyet_marj", "%", True),
    ("Fiili Net Marj (vergi öncesi)", "fiili_net_marj", "%", True),
    ("Brüt Marj", "brut_marj", "%", True), ("Faaliyet Marjı", "faaliyet_marj", "%", True),
    ("Net Marj", "net_marj", "%", True), ("Özkaynak Kârlılığı (ROE)", "roe", "%", True),
    ("Aktif Kârlılığı (ROA)", "roa", "%", True),
    ("Stok Devir Hızı", "stok_devir", "kez/yıl", True),
    ("Stok Bekleme Süresi", "stok_gun", "gün", False),
    ("Stok / Net Satış", "stok_satis", "%", False),
    ("Alacak Tahsil Süresi (DSO)", "dso", "gün", False),
    ("Gecikmiş Alacak Oranı", "gecikme_orani", "%", False),
    ("Cari Oran", "cari_oran", "x", True), ("Asit-Test", "asit_test", "x", True),
    ("Borç / Özkaynak", "borc_ozkaynak", "x", False),
    ("Banka Kredisi / Aktif", "kredi_aktif", "%", False),
    ("Finansman Gideri / Net Satış", "finansman_yuku", "%", False),
)


# Bir kalemin yıllar arası yayılımı en büyük değerinin bu oranından azsa «kıpırdamıyor»
# sayılır. Birebir eşitlik aramak yetmiyordu: kuruş farkıyla değişen ama fiilen donmuş
# satırlar kaçıyordu (canlıda kullanıcı bu tutarsızlığı sordu).
_KIPIRTI_ESIGI = 0.005   # %0,5


def _kiyas_degeri_yok(degerler: list[float | None]) -> bool:
    """
    Bu satır yıllar arası bir şey anlatıyor mu?

    Anlatmıyorsa TABLOYA HİÇ GİRMEZ. Uyarı işaretiyle göstermek kalabalık yapıyordu:
    «hepsi aynı» bir karşılaştırma değildir. Üç durum bilgisizdir — hiçbir yıl için
    hesaplanamayan, tüm yıllarda sıfır olan ve fiilen hiç kıpırdamayan satırlar.
    """
    dolu = [d for d in degerler if d is not None]
    if len(dolu) < 2 or len(dolu) != len(degerler):
        return not dolu            # kısmen hesaplanabilen satır bilgi taşır
    buyuk = max(abs(d) for d in dolu)
    if buyuk < 0.005:
        return True                # hepsi sıfır
    return (max(dolu) - min(dolu)) <= buyuk * _KIPIRTI_ESIGI


def kiyas_tabani(oncekiler: list[float | None]) -> float | None:
    """
    Değişim sütununun tabanı: ÖNCEKİ YILLARIN ORTALAMASI.

    Eskiden yalnız İLK yılla son yıl kıyaslanıyordu; sütun başlığı «2020→2026» derken
    aradaki 2021-2025 hiç hesaba girmiyordu — kullanıcı haklı olarak «tabloda altı yıl
    var, kıyas iki yıl» dedi. Tek bir yılı taban almak, o yılın kendi olağandışılığını
    (tek seferlik büyük satış, kur şoku) trend sanmaya da yol açar.

    Hesaplanamayan yıllar ortalamaya girmez; hiçbiri hesaplanamıyorsa taban yoktur.
    """
    dolu = [d for d in oncekiler if d is not None]
    return (sum(dolu) / len(dolu)) if dolu else None


def degisim_basligi(yillar: list[int]) -> str:
    """
    Değişim sütununun başlığı — neyin neye oranlandığı BAŞLIKTA yazar.

    İki sütun varken ortalama tek bir yıl demektir; o zaman «2025→2026» daha dürüst.
    """
    if len(yillar) < 2:
        return ""
    if len(yillar) == 2:
        return f"{yillar[0]}→{yillar[1]}"
    return f"{yillar[-1]} / önceki ort."


def _degisim(ilk: float | None, son: float | None, birim: str,
             artis_iyi: bool | None) -> tuple[str, bool | None]:
    """
    Kıyas tabanından son yıla değişim.

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

    def satir(etiket: str, degerler: list[float | None], birim: str,
              artis_iyi: bool | None,
              kiyas: list[float | None] | None = None) -> TabloSatir:
        """
        `kiyas`: sabitlik hangi seriye bakılarak ölçülsün (verilmezse kendisi).

        Dolar satırlarında bu ŞART: TL'de hiç kıpırdamayan bir kalem, kur değiştiği
        için dolar bazında oynuyormuş gibi görünür. Aynı boş bilgi, kılık değiştirmiş
        hâli — kullanıcı canlıda fark etti.
        """
        metin, iyi = _degisim(kiyas_tabani(degerler[:-1]), degerler[-1], birim, artis_iyi)
        return TabloSatir(
            etiket=etiket,
            hucreler=[_oran_metni(d, birim) for d in degerler],
            degerler=list(degerler),
            degisim=metin, iyi=iyi,
            eksi=[d is not None and d < 0 for d in degerler],
            sabit=_kiyas_degeri_yok(kiyas if kiyas is not None else degerler),
        )

    def bolum(baslik: str, tarif, deger, birim: str, *, tl_kiyas: bool = False) -> TabloBolum:
        return TabloBolum(baslik, [
            satir(etiket, [deger(k, alan) for k in s], birim, artis_iyi,
                  kiyas=[k.kalem(alan) for k in s] if tl_kiyas else None)
            for etiket, alan, artis_iyi in tarif
        ])

    bolumler: list[TabloBolum] = []
    if all(k.doviz_var for k in s):
        usd = TabloBolum("DOLAR BAZINDA (USD)")
        usd.satirlar.append(
            satir("TL/USD kuru (dönem sonu)", [k.kur_son for k in s], "x", None))
        usd.satirlar.append(
            satir("Net Satışlar", [k.satis_usd for k in s], "USD", True))
        # tl_kiyas: sabitlik TL tutarından ölçülür — kur oynamasını hareket sanmayalım.
        usd.satirlar += bolum("", _USD_AKIS, lambda k, a: k.usd_akis(k.kalem(a)),
                              "USD", tl_kiyas=True).satirlar
        # Canlı ayak kalem() süzgecinden GEÇMEZ: maliyet_eksik bu satırları etkilemiyor.
        usd.satirlar += bolum("", _USD_FIILI, lambda k, a: k.usd_akis(getattr(k, a)),
                              "USD", tl_kiyas=True).satirlar
        usd.satirlar += bolum("", _USD_BAKIYE, lambda k, a: k.usd(k.kalem(a)),
                              "USD", tl_kiyas=True).satirlar
        bolumler.append(usd)

    bolumler.append(TabloBolum("ORANLAR VE DEVİR HIZLARI", [
        satir(etiket + (" (%)" if birim == "%" else "" if birim == "x" else f" ({birim})"),
              [k.kalem(alan) for k in s], birim, artis_iyi)
        for etiket, alan, birim, artis_iyi in _ORAN_SATIR
    ]))

    # KIPIRDAMAYAN SATIRLAR HİÇ GÖSTERİLMEZ. Tüm yıllarda aynı kalan kalem bir
    # karşılaştırma değildir; uyarı işaretiyle göstermek tabloyu kalabalıklaştırıp
    # okuyucuyu meşgul ediyordu. Boşalan bölüm de düşer.
    ayikli = []
    for b in bolumler:
        kalan = [r for r in b.satirlar if not r.sabit]
        if kalan:
            ayikli.append(TabloBolum(b.baslik, kalan))
    return yillar, ayikli


def ortak_pencere(kapanislar: list[YilKapanis]) -> str:
    """
    Bütün sütunlar AYNI ay-gün penceresini kullanıyorsa o pencere («28.07 – 28.07»).

    «Geçmiş yılların aynı dönemi» modunda her sütun aynı takvim penceresidir; başlığa
    tam tarih yazmak (28.07.2021–28.07.2022 …) altı sütunda okunamaz hâle geliyordu.
    Ortak pencere bir kez kartın başlığında söylenir, sütunlarda yalnız yıl kalır.
    Pencereler farklıysa boş döner — o zaman her sütun kendi tarihini yazmak ZORUNDA.
    """
    gecerli = [k for k in kapanislar if len(k.bas) == 10 and len(k.bit) == 10]
    if len(gecerli) < 2:
        return ""
    kume = {(k.bas[5:], k.bit[5:]) for k in gecerli}
    if len(kume) != 1:
        return ""
    b, s = kume.pop()
    return f"{b[3:5]}.{b[:2]} – {s[3:5]}.{s[:2]}"


def yillar_arasi_csv(kapanislar: list[YilKapanis]) -> str:
    """
    Modele giden yıllar arası tablo — ekrandakiyle AYNI satırlardan, ham rakamlarla.

    Ekran kısaltılmış tutar gösterir (41,2 milyon); model tam sayı görür. Satır kümesi
    tek kaynaktan (yillar_tablosu) geldiği için ikisi ayrışamaz.
    """
    yillar, bolumler = yillar_tablosu(kapanislar)
    if not yillar:
        return ""
    sirali = sorted(kapanislar, key=lambda k: k.yil)

    ortak = ortak_pencere(sirali)
    out = ["Kalem;" + ";".join(
        (str(k.yil) if ortak else k.basligi()) for k in sirali)]
    if ortak:
        out.append(
            f"NOT;Her sütun {ortak} penceresidir — hepsi AYNI uzunlukta, bu yüzden akış "
            "kalemleri (satış, kâr) doğrudan kıyaslanabilir. Kullanıcı geçmiş yıllarla "
            "karşılaştırmayı açıkça istedi.")
    else:
        out.append(
            "NOT;Her sütun, SEÇİLEN TARİH ARALIĞININ o yıla düşen parçasıdır — "
            "başlıktaki gün aralığı budur. Aralık dışından tek gün bile okunmaz. "
            "Sütunlar FARKLI UZUNLUKTA olabilir; akış kalemlerini (satış, kâr) "
            "kıyaslarken bunu hesaba kat, aylığa indirmeden yorum yapma.")
    out.append(
        "KAYNAK;Yıllık Net Satışlar = muhasebe gelir tablosu (GL 60/61). "
        "Aylık Satış satırlarıyla aynı kaynak değildir."
    )
    if len(sirali) > 2:
        out.append(
            f"NOT;Ekrandaki tabloda son sütun {sirali[-1].yil} yılını, önceki "
            f"{len(sirali) - 1} yılın ORTALAMASINA oranlar. Sen de gidişatı tek bir "
            "geçmiş yılla değil, geçmişin bütünüyle kıyasla.")
    for bolum in bolumler:
        if bolum.baslik:
            out.append("")
            out.append(f"--- {bolum.baslik} ---")
        for satir in bolum.satirlar:
            hucre = ["" if d is None else csv_sayi(d) for d in satir.degerler]
            out.append(satir.etiket.replace(";", ",") + ";" + ";".join(hucre))

    out.append("")
    out.append("KAYNAK;Ticari Alacak / Ticari Borç / vadesi geçmiş = CARİ HESAP "
               "HAREKETLERİ (Alacak & Borç sekmesiyle aynı). Nakit = 100/101/102/108 "
               "GL bakiyesi (Nakit Akış sekmesiyle aynı). Stok, özkaynak, aktif ve "
               "kısa/uzun vadeli borç = MİZAN. Mizan ile cari çelişirse cari daha "
               "günceldir; hangisine dayandığını yaz.")
    out.append("NOT;Yıllar boyunca hiç değişmeyen kalemler tablodan ÇIKARILMIŞTIR "
               "(karşılaştırma değeri yok). Görmediğin bir kalem hakkında çıkarım yapma.")

    for k in sirali:
        if not k.tam:
            out.append(f"NOT;{k.yil} yılı TAMAMLANMADI — rakamlar yılın tamamını "
                       "kapsamaz. Yalnız aynı tarih penceresiyle hazırlanmış diğer YTD "
                       "sütunlarıyla kıyaslanmalıdır.")
        if k.maliyet_eksik:
            out.append(
                f"NOT;{k.yil} yılında satışların maliyeti (62) muhasebeye işlenmemiş. "
                "Eksik olan «621 SMM / 153 Ticari Mallar» fişinin iki ayağı var: 621 "
                "borçlanmadığı için KÂR, 153 alacaklanmadığı için STOK aynı tutarda "
                "şişer. Bu yüzden o yılın kâr kalemleri, stoğu, özkaynağı, aktif "
                "toplamı ve bunlardan türeyen oranları BOŞ bırakıldı — boş hücreyi "
                "«sıfır» ya da «değişmedi» diye yorumlama. Asit-Test etkilenmez.")
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
                   + f";{degisim_basligi(yillar)}")
        for bolum in bolumler:
            if bolum.baslik:
                out.append(f"MUKAYESE;{bolum.baslik}")
            for satir in bolum.satirlar:
                # CSV'ye HAM rakam gider: ekrandaki «176 bin» yuvarlaması Excel'de
                # hesap yapmayı imkânsız kılar ve yıllar arası farkı gizler.
                hucre = ["" if d is None else csv_sayi(d) for d in satir.degerler]
                out.append("MUKAYESE;" + ";".join(
                    [satir.etiket.replace(";", ","), *hucre, satir.degisim]))
        out.append("")

    for satir in y.metin.splitlines():
        temiz = satir.replace(";", ",").strip()
        if temiz:
            out.append(f"YORUM;{temiz}")
    return "\r\n".join(out)
