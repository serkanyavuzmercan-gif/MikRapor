"""
Tahmin motoru — geleceğe dönük ciro / brüt kâr / net kâr / nakit projeksiyonu.

Hibrit: varsayımlar (baz ciro, aylık büyüme %, brüt marj %, sabit gider) geçmiş veriden otomatik
önerilir (oner_varsayim) ama kullanıcı düzenleyip senaryo değiştirebilir. build_tahmin saf bir
fonksiyondur (Mikro'ya gitmez) → kullanıcı her oynadığında anında yeniden hesaplanır.

Model (aylık, n = 1..ufuk):
  ciro_n      = baz_ciro × (1 + büyüme)^n
  brüt_kâr_n  = ciro_n × marj
  net_kâr_n   = brüt_kâr_n − sabit_gider
  nakit_n     = nakit_(n-1) + net_kâr_n      (basit: kâr nakde döner; tahsilat gecikmesi yok)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from domain.ortak import csv_sayi


def ogrenme_penceresi_bas(bas: str, bit: str, *, ay: int = 12) -> str:
    """
    Varsayım öğrenme penceresinin başlangıç tarihi (YYYY-MM-DD).

    SEÇİLEN TARİH ARALIĞININ DIŞINA ÇIKMAZ. Pencere «bit'ten `ay` ay geri»dir, ama
    asla `bas`tan öncesine gitmez.

    Eskiden ikisinin ERKENİ alınıyordu: dar dönem seçen kullanıcı için pencere geriye
    doğru 12 aya genişletiliyordu. Gerekçesi vardı (tek çeyrekte marj %49 çıkıp 12 ayda
    ~%25'e oturuyor), ama kullanıcının seçimini eziyordu — seçmediği günlerin verisi
    rapora giriyordu. Kullanıcı bunu açıkça reddetti: «tarih aralığı kutsal, her şeyi o
    belirliyor». Pencere kısalıyorsa kısalsın; dar dönemin dalgalı çıkması kullanıcının
    bilerek aldığı sonuçtur.
    """
    try:
        y, m, d = int(bit[:4]), int(bit[5:7]), int(bit[8:10])
    except (ValueError, IndexError):
        return bas
    yil_geri, ay_idx = divmod((y * 12 + (m - 1)) - ay, 12)
    try:
        geri = date(yil_geri, ay_idx + 1, d)
    except ValueError:
        geri = date(yil_geri, ay_idx + 1, 28)  # 31/29 gün taşması
    g = geri.isoformat()
    return max(bas, g) if bas else g


def _ay_ekle(yyyymm: str, k: int) -> str:
    """'2026-06' + k ay → 'YYYY-MM'."""
    try:
        y, m = int(yyyymm[:4]), int(yyyymm[5:7])
    except (ValueError, IndexError):
        return ""
    idx = y * 12 + (m - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def aylik_buyume_oner(seri: list[float], alt: float = -15.0, ust: float = 20.0) -> float:
    """Aylık seriden bileşik aylık büyüme (%) önerir, [alt, ust] aralığına kırpar."""
    vals = [v for v in seri if v and v > 0]
    if len(vals) < 2:
        return 0.0
    n = len(vals) - 1
    oran = (vals[-1] / vals[0]) ** (1.0 / n) - 1.0
    return max(alt, min(ust, oran * 100.0))


@dataclass
class TahminVarsayim:
    baslangic_ay: str = ""        # 'YYYY-MM' — projeksiyon bunun ERTESİ ayından başlar
    baslangic_nakit: float = 0.0
    baz_ciro: float = 0.0         # aylık ciro tabanı (1. tahmin ayı)
    buyume_yuzde: float = 0.0     # aylık büyüme %
    marj_yuzde: float = 0.0       # brüt marj %
    sabit_gider: float = 0.0      # aylık sabit/işletme gideri
    kart_borcu_acik: float = 0.0  # projeksiyon başlangıcında ödenmemiş kart borcu
    kart_borcu_odeme_yuzde: float = 25.0  # aylık ödeme oranı - senaryo varsayımı
    # Ödenmeyen kart borcuna işleyen aylık faiz. Reel Değer sekmesinden BURAYA taşındı:
    # kart borcu zaten burada modelleniyordu (bakiye + ödeme oranı + aylık ödeme sütunu),
    # yalnız faiz eksikti. Aynı konuyu iki sekmede göstermek kural 5'e aykırıydı.
    kart_aylik_faiz_yuzde: float = 0.0
    ufuk_ay: int = 12

    def ozet(self) -> str:
        return (f"baz ciro {self.baz_ciro:,.0f} · büyüme %{self.buyume_yuzde:.1f}/ay · "
                f"marj %{self.marj_yuzde:.1f} · sabit gider {self.sabit_gider:,.0f} · "
                f"kart borcu {self.kart_borcu_acik:,.0f} / %{self.kart_borcu_odeme_yuzde:.0f}").replace(",", ".")


@dataclass
class AyTahmin:
    ay: str
    ciro: float = 0.0
    brut_kar: float = 0.0
    sabit_gider: float = 0.0
    kart_borcu_odeme: float = 0.0
    kart_borcu_kalan: float = 0.0
    kart_finansman: float = 0.0     # o ay taşınan borca işleyen faiz
    net_kar: float = 0.0
    net_nakit: float = 0.0
    nakit: float = 0.0


@dataclass
class Tahmin:
    varsayim: TahminVarsayim = field(default_factory=TahminVarsayim)
    aylar: list = field(default_factory=list)
    toplam_ciro: float = 0.0
    toplam_brut: float = 0.0
    toplam_net: float = 0.0
    toplam_net_nakit: float = 0.0
    toplam_kart_borcu_odeme: float = 0.0
    toplam_kart_finansman: float = 0.0
    kalan_kart_borcu: float = 0.0

    @property
    def eksi_ay_sayisi(self) -> int:
        """Nakitin eksi olduğu ay sayısı."""
        return sum(1 for a in self.aylar if a.nakit < 0)

    @property
    def kalici_eksi(self) -> bool:
        """
        Dönem SONUNDA da eksi mi?

        «Bir ay eksiye düşüp toparlamak» ile «eksiyle bitirmek» aynı şey değil ve
        kullanıcının yapacağı iş de aynı değil: ilki köprü finansman, ikincisi
        büyüme/marj/gider kararı. Uyarı metni bunları ayırmak zorunda.
        """
        return bool(self.aylar) and self.aylar[-1].nakit < 0

    @property
    def dip_ayi(self):
        """En düşük nakdin yaşandığı ay (AyTahmin) — sebebini söyleyebilmek için."""
        return min(self.aylar, key=lambda a: a.nakit) if self.aylar else None

    @property
    def dip_sebebi_kart(self) -> bool:
        """Dip, o ay ödenen kredi kartı borcuyla tek başına açıklanıyor mu?"""
        ay = self.dip_ayi
        return bool(ay and ay.nakit < 0 and ay.kart_borcu_odeme >= abs(ay.nakit))
    son_nakit: float = 0.0
    en_dusuk_nakit: float = 0.0
    en_dusuk_ay: str = ""


def build_tahmin(v: TahminVarsayim) -> Tahmin:
    """Varsayımlardan aylık projeksiyon üretir (saf fonksiyon)."""
    t = Tahmin(varsayim=v)
    g = v.buyume_yuzde / 100.0
    marj = v.marj_yuzde / 100.0
    nakit = v.baslangic_nakit
    kalan_kart_borcu = max(0.0, v.kart_borcu_acik)
    kart_orani = min(100.0, max(0.0, v.kart_borcu_odeme_yuzde)) / 100.0
    kart_faiz = max(0.0, v.kart_aylik_faiz_yuzde) / 100.0
    en_dusuk = nakit
    en_dusuk_ay = v.baslangic_ay
    for n in range(1, max(0, v.ufuk_ay) + 1):
        ciro = v.baz_ciro * ((1.0 + g) ** n)
        brut = ciro * marj
        kart_odeme = min(kalan_kart_borcu, kalan_kart_borcu * kart_orani)
        # Ödenmeyen kısma faiz işler; %100 ödemede taşınan borç kalmaz, maliyet doğmaz.
        tasinan = kalan_kart_borcu - kart_odeme
        kart_faiz_tutari = tasinan * kart_faiz
        kalan_kart_borcu = tasinan + kart_faiz_tutari
        # Kart borcu ödemesi kâr/gider değil, mevcut yükümlülüğün nakit ödemesidir.
        # Bu nedenle kârı ayrı tutup yalnızca nakit değişimine ekliyoruz.
        net = brut - v.sabit_gider
        net_nakit = net - kart_odeme
        nakit += net_nakit
        ay = _ay_ekle(v.baslangic_ay, n)
        t.aylar.append(AyTahmin(
            ay=ay, ciro=ciro, brut_kar=brut, sabit_gider=v.sabit_gider,
            kart_borcu_odeme=kart_odeme, kart_borcu_kalan=kalan_kart_borcu,
            kart_finansman=kart_faiz_tutari,
            net_kar=net, net_nakit=net_nakit, nakit=nakit,
        ))
        if nakit < en_dusuk:
            en_dusuk, en_dusuk_ay = nakit, ay
    t.toplam_ciro = sum(a.ciro for a in t.aylar)
    t.toplam_brut = sum(a.brut_kar for a in t.aylar)
    t.toplam_net = sum(a.net_kar for a in t.aylar)
    t.toplam_net_nakit = sum(a.net_nakit for a in t.aylar)
    t.toplam_kart_borcu_odeme = sum(a.kart_borcu_odeme for a in t.aylar)
    t.toplam_kart_finansman = sum(a.kart_finansman for a in t.aylar)
    t.kalan_kart_borcu = kalan_kart_borcu
    t.son_nakit = t.aylar[-1].nakit if t.aylar else v.baslangic_nakit
    t.en_dusuk_nakit = en_dusuk
    t.en_dusuk_ay = en_dusuk_ay
    return t


def oner_varsayim(
    *,
    satis_serisi: list[float],
    brut_marj_yuzde: float,
    baslangic_nakit: float,
    aylik_sabit_gider: float,
    baslangic_ay: str,
    kart_borcu_acik: float = 0.0,
    kart_borcu_odeme_yuzde: float = 25.0,
    kart_aylik_faiz_yuzde: float = 0.0,
    ufuk_ay: int = 12,
) -> TahminVarsayim:
    """Geçmiş aylık satış serisi + marj + nakit + gideri varsayım taslağına çevirir."""
    pozitif = [v for v in satis_serisi if v and v > 0]
    if pozitif:
        # Baz ciro: son 3 ayın ortalaması (yoksa tüm ortalama)
        son = pozitif[-3:] if len(pozitif) >= 3 else pozitif
        baz = sum(son) / len(son)
    else:
        baz = 0.0
    return TahminVarsayim(
        baslangic_ay=baslangic_ay,
        baslangic_nakit=baslangic_nakit,
        baz_ciro=baz,
        buyume_yuzde=aylik_buyume_oner(satis_serisi),
        marj_yuzde=brut_marj_yuzde,
        sabit_gider=max(0.0, aylik_sabit_gider),
        kart_borcu_acik=max(0.0, kart_borcu_acik),
        kart_borcu_odeme_yuzde=min(100.0, max(0.0, kart_borcu_odeme_yuzde)),
        kart_aylik_faiz_yuzde=max(0.0, kart_aylik_faiz_yuzde),
        ufuk_ay=ufuk_ay,
    )


def tahmin_csv(t: Tahmin) -> str:
    """Tahmin projeksiyonunu CSV'ye çevirir (; ayraç, Türkçe ondalık)."""
    s = csv_sayi

    v = t.varsayim
    out = ["Bölüm;Kalem;Değer"]
    out.append(f"VARSAYIM;Başlangıç Nakit;{s(v.baslangic_nakit)}")
    out.append(f"VARSAYIM;Baz Aylık Ciro;{s(v.baz_ciro)}")
    out.append(f"VARSAYIM;Aylık Büyüme %;{s(v.buyume_yuzde)}")
    out.append(f"VARSAYIM;Brüt Marj %;{s(v.marj_yuzde)}")
    out.append(f"VARSAYIM;Aylık Sabit Gider;{s(v.sabit_gider)}")
    out.append(f"VARSAYIM;Açık Kredi Kartı Borcu;{s(v.kart_borcu_acik)}")
    out.append(f"VARSAYIM;Kart Borcu Ödeme Oranı %;{s(v.kart_borcu_odeme_yuzde)}")
    out.append(f"VARSAYIM;Kredi Kartı Aylık Faizi %;{s(v.kart_aylik_faiz_yuzde)}")
    out.append("PROJEKSİYON;Ay;Ciro;Brüt Kâr;Kart Borcu Ödemesi;Net Kâr;Net Nakit;Nakit")
    for a in t.aylar:
        out.append(
            f"AY;{a.ay};{s(a.ciro)};{s(a.brut_kar)};{s(a.kart_borcu_odeme)};"
            f"{s(a.net_kar)};{s(a.net_nakit)};{s(a.nakit)}"
        )
    out.append(f"TOPLAM;Ciro;{s(t.toplam_ciro)}")
    out.append(f"TOPLAM;Brüt Kâr;{s(t.toplam_brut)}")
    out.append(f"TOPLAM;Net Kâr;{s(t.toplam_net)}")
    out.append(f"TOPLAM;Kart Borcu Ödemesi;{s(t.toplam_kart_borcu_odeme)}")
    out.append(f"TOPLAM;Net Nakit Etkisi;{s(t.toplam_net_nakit)}")
    out.append(f"TOPLAM;Kart Finansman Maliyeti;{s(t.toplam_kart_finansman)}")
    out.append(f"TOPLAM;Kalan Kart Borcu;{s(t.kalan_kart_borcu)}")
    out.append(f"TOPLAM;Dönem Sonu Nakit;{s(t.son_nakit)}")
    out.append(f"TOPLAM;En Düşük Nakit ({t.en_dusuk_ay});{s(t.en_dusuk_nakit)}")
    return "\r\n".join(out)
