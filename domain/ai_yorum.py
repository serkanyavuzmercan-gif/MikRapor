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
fotoğrafıyla yetinme.
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

## Bu Ay Yapılacak 3 İş
Somut ve uygulanabilir olsun. "Kârlılığı artırın" değil, "X vadesi geçmiş 1,2M \
alacağın tahsilatına odaklanın" gibi.

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
    ozkaynak: float = 0.0
    aktif_toplam: float = 0.0
    maliyet_eksik: bool = False    # 62 (SMM) girilmemiş → kâr şişik görünür

    def _marj(self, pay: float) -> float:
        return (pay / self.net_satis * 100) if self.net_satis else 0.0

    @property
    def brut_marj(self) -> float:
        return self._marj(self.brut_kar)

    @property
    def net_marj(self) -> float:
        return self._marj(self.net_kar)


# Yıllar arası tabloda gösterilecek kalemler — az ve karşılaştırılabilir olanlar.
_YIL_KALEMLERI: tuple[tuple[str, str], ...] = (
    ("Net Satışlar", "net_satis"),
    ("Brüt Kâr", "brut_kar"),
    ("Faaliyet Kârı", "faaliyet_kari"),
    ("Dönem Net Kârı", "net_kar"),
    ("Nakit (dönem sonu)", "nakit"),
    ("Ticari Alacak (dönem sonu)", "alacak"),
    ("Stok (dönem sonu)", "stok"),
    ("Kısa Vadeli Borç (dönem sonu)", "kvyk"),
    ("Özkaynak (dönem sonu)", "ozkaynak"),
    ("Aktif Toplam (dönem sonu)", "aktif_toplam"),
)


def yillar_arasi_csv(kapanislar: list[YilKapanis]) -> str:
    """Yılları yan yana koyan karşılaştırma tablosu — trendi tek bakışta görünür kılar."""
    if len(kapanislar) < 2:
        return ""
    sirali = sorted(kapanislar, key=lambda k: k.yil)
    out = ["Kalem;" + ";".join(str(k.yil) for k in sirali)]
    for etiket, alan in _YIL_KALEMLERI:
        out.append(etiket + ";" + ";".join(csv_sayi(getattr(k, alan)) for k in sirali))
    out.append("Brüt Marj (%);" + ";".join(csv_sayi(k.brut_marj) for k in sirali))
    out.append("Net Marj (%);" + ";".join(csv_sayi(k.net_marj) for k in sirali))

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
    yillar: list[int] = field(default_factory=list)   # çok yıllı analizde kapsanan yıllar

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
    yillar: list[int] | None = None,
) -> AiVeriPaketi:
    """Rapor CSV'lerinden veri paketini kurar; boş/hatalı bölümler elenir."""
    temiz: list[tuple[str, str]] = []
    for baslik, icerik in bolumler or []:
        if icerik and icerik.strip():
            temiz.append((baslik, icerik))
    return AiVeriPaketi(
        yil=yil, bas=bas, bit=bit, firma=firma, bolumler=temiz,
        bugun=bugun, tamamlandi=tamamlandi, ay_sayisi=ay_sayisi,
        yillar=sorted(yillar or []))


def ai_yorum_csv(y: AiYorum) -> str:
    """Yorumu Türkçe Excel uyumlu CSV'ye çevirir (satır satır metin)."""
    out = ["Bölüm;İçerik"]
    out.append(f"DÖNEM;{y.aralik}")
    out.append(f"SAĞLAYICI;{y.saglayici}")
    out.append(f"MODEL;{y.model}")
    out.append(f"TOKEN;girdi {csv_sayi(y.girdi_token)} / çıktı {csv_sayi(y.cikti_token)}")
    for satir in y.metin.splitlines():
        temiz = satir.replace(";", ",").strip()
        if temiz:
            out.append(f"YORUM;{temiz}")
    return "\r\n".join(out)
