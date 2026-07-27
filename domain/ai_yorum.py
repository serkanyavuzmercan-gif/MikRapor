"""
Yapay Zekâ Yorumu — rapor verisini paketleyen ve yorumu taşıyan saf katman.

Burada ağ çağrısı YOKTUR (bkz. infra/ai_client.py). Bu modül yalnız:
  • seçili yılın tüm rapor verisini tek bir metin pakete çevirir (build_ai_veri_paketi),
  • modele verilecek yönergeyi tutar (SISTEM_PROMPT),
  • dönen yorumu taşır (AiYorum) ve CSV'ye çevirir.

Paket, her raporun kendi CSV üreticisinden kurulur — ekranda gördüğün rakamla modele
giden rakam aynı kaynaktan gelsin diye. Cari listeleri kırpılmaz: kullanıcı ham veri
paylaşımını açıkça onayladığında ünvanlar dâhil tüm kırılım gider.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.ortak import csv_sayi

# Model, finans okuryazarlığı olmayan bir KOBİ sahibine yazıyor. Yönerge bilinçli olarak
# "ne yapmalıyım" odaklı: teşhis değil, karar. Uydurma rakamı önlemek için veri dışına
# çıkmaması ve eksik veriyi eksik demesi ayrıca istenir.
SISTEM_PROMPT = """\
Sen bir KOBİ'nin mali danışmanısın. Karşındaki kişi işini iyi bilir ama finans \
okuryazarı DEĞİLDİR: "cari oran", "DSO", "işletme sermayesi" gibi terimleri bilmez.

Sana bir Türk şirketinin bir yıllık muhasebe ve cari verisi CSV bölümleri hâlinde \
verilecek. Bu veriye bakarak Türkçe bir yönetim yorumu yaz.

KURALLAR
- Sadece verilen veriye dayan. Veride olmayan bir rakamı ASLA uydurma.
- Bir şeyi veriden çıkaramıyorsan "bu veriyle söylenemez" de; tahmin yürütme.
- Verinin başındaki «DÖNEM DURUMU» bloğuna MUTLAKA uy. Dönem devam ediyorsa yılı \
bitmiş gibi anlatma ve resmî kârı olduğu gibi doğru kabul etme.
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
            f"VERİ ARALIĞI: {self.bas} – {self.bit}",
            "",
            self.donem_notu,
            "",
        ]
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
) -> AiVeriPaketi:
    """Rapor CSV'lerinden veri paketini kurar; boş/hatalı bölümler elenir."""
    temiz: list[tuple[str, str]] = []
    for baslik, icerik in bolumler or []:
        if icerik and icerik.strip():
            temiz.append((baslik, icerik))
    return AiVeriPaketi(
        yil=yil, bas=bas, bit=bit, firma=firma, bolumler=temiz,
        bugun=bugun, tamamlandi=tamamlandi, ay_sayisi=ay_sayisi)


def ai_yorum_csv(y: AiYorum) -> str:
    """Yorumu Türkçe Excel uyumlu CSV'ye çevirir (satır satır metin)."""
    out = ["Bölüm;İçerik"]
    out.append(f"DÖNEM;{y.bas} - {y.bit}")
    out.append(f"SAĞLAYICI;{y.saglayici}")
    out.append(f"MODEL;{y.model}")
    out.append(f"TOKEN;girdi {csv_sayi(y.girdi_token)} / çıktı {csv_sayi(y.cikti_token)}")
    for satir in y.metin.splitlines():
        temiz = satir.replace(";", ",").strip()
        if temiz:
            out.append(f"YORUM;{temiz}")
    return "\r\n".join(out)
