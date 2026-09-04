"""
Kurgu firmanın defteri — tek aylık iş modelinden türeyen ham satırlar.

TEK MODEL, DOKUZ SEKME: satış, alış, gider, tahsilat ve ödeme yalnız burada, ay ay
tanımlanır (`ay_kaydi`). Mizan da, stok hareketi de, cari açık kalem de, GL nakit
fişi de aynı sayılardan türer. Ayrı ayrı uydurulsalardı Nakit Akış'ın «kapanış
nakdi» ile Bilanço'nun «102 Bankalar»ı tutmazdı ve demo, olmayan bir hatayı
varmış gibi gösterirdi.

RASTGELELİK YOK: her şey ay indeksinden saf formülle çıkar. Tohumlu `random` bile
kullanılmadı — kütüphane sürümü değişince aynı ekran görüntüsü bir daha üretilemez.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

FIRMA_ADI = "ÖRNEK SANAYİ VE TİCARET A.Ş."

# Defterin kapsadığı aralık. Kullanıcının seçebileceği her tarih burada olmalı:
# kural 1 gereği aralık dışına çıkılmaz, defter kısa kalırsa sekmeler «—» gösterir
# ve ekran görüntüsü «program çalışmıyor» gibi durur.
ILK_AY = date(2024, 1, 1)
SON_AY = date(2026, 12, 1)

KDV_ORAN = 0.20
ACILIS_NAKIT = 1_850_000.0     # 01.01.2024 banka+kasa
SERMAYE = 5_000_000.0

# Mevsim çarpanı — sanayi firmasının tipik seyri: yaz ortası ve ocak durgun.
_MEVSIM = {1: 0.84, 2: 0.90, 3: 1.06, 4: 1.09, 5: 1.12, 6: 1.05,
           7: 0.92, 8: 0.79, 9: 1.08, 10: 1.15, 11: 1.11, 12: 0.98}

# Satışa oranla gider yapısı. KURGU FİRMA AYAKTA DURMALI: ilk kalibrasyonda
# çıkışlar girişleri aşıyordu ve demo, ekranda kapanış nakdi −928.630 TL olan,
# dönem zararı yazan bir firma gösteriyordu. Ürünün vitrini o değil — ama rakamlar
# «her ay kâr» diye uydurulmuş da değil: aşağıdaki oranlar birbirine bağlı ve
# tutarlılık (marj, stok birikimi, nakit birikimi) buradan ÇIKAR, elle yazılmaz.
_SMM_ORANI = 0.700        # brüt marj %30
_ALIS_ORANI = 0.720       # alış > SMM: stok yavaşça birikir
_PERSONEL_ORANI = 0.088
_GENEL_ORANI = 0.046
_SGK_ORANI = 0.028
_KURUMLAR_ORANI = 0.018
_TAHSILAT_ORANI = 0.97    # brüt satışın tahsil edilen kısmı (2 ay sonra)
_ODEME_ORANI = 0.93       # brüt alışın ödenen kısmı (1 ay sonra)


@dataclass(frozen=True)
class AyKaydi:
    """Bir ayın işi. Tutarlar TL; satış/alış KDV HARİÇ, tahsilat/ödeme KDV DÂHİL."""

    ay: date
    satis_net: float
    alis_net: float
    personel: float
    genel_gider: float
    amortisman: float
    faiz: float
    tahsilat: float
    satici_odeme: float
    vergi_odeme: float
    sgk_odeme: float
    kredi_kullanim: float
    kredi_odeme: float

    @property
    def etiket(self) -> str:
        return f"{self.ay.year:04d}-{self.ay.month:02d}"

    @property
    def satis_brut(self) -> float:
        return self.satis_net * (1 + KDV_ORAN)

    @property
    def alis_brut(self) -> float:
        return self.alis_net * (1 + KDV_ORAN)

    @property
    def smm(self) -> float:
        """
        Satılan malın maliyeti — brüt marj %30.

        ALIŞTAN KÜÇÜK OLMAK ZORUNDA (`_ALIS_ORANI` > `_SMM_ORANI`): aksi hâlde
        kümülatif stok eksiye iner ve bilançoda «153 Ticari Mallar −685.271» gibi
        muhasebeten imkânsız bir satır çıkar. İlk kalibrasyonda tam bu oldu.
        """
        return self.satis_net * _SMM_ORANI

    @property
    def nakit_giris(self) -> float:
        return self.tahsilat + self.kredi_kullanim

    @property
    def nakit_cikis(self) -> float:
        return (self.satici_odeme + self.personel + self.genel_gider
                + self.vergi_odeme + self.sgk_odeme + self.kredi_odeme + self.faiz)


def _ay_indeksi(ay: date) -> int:
    return (ay.year - ILK_AY.year) * 12 + (ay.month - ILK_AY.month)


def _satis_net(i: int) -> float:
    """
    Ay indeksinden satış — SAF FORMÜL, özyineleme YOK.

    Bu fonksiyon bir zamanlar `ay_kaydi` üzerinden geçmiş ayları çağırıyordu;
    `ay_kaydi` da tahsilat için iki ay geriyi çağırdığı için çağrı ağacı Fibonacci
    gibi ikiye katlanıyordu ve 30. ayda test donuyordu. Geçmiş ay bir FORMÜLDÜR,
    bir arama değil.

    `i < 0` defter öncesi aylardır (ilk ayların devir tahsilatı); aynı formül
    negatif indekste de çalışır.
    """
    ay = ((ILK_AY.month - 1 + i) % 12) + 1
    return 3_450_000.0 * (1 + 0.0115 * i) * _MEVSIM[ay]


def _alis_net(i: int) -> float:
    ay = ((ILK_AY.month - 1 + i) % 12) + 1
    return _satis_net(i) * _ALIS_ORANI * (1.03 if ay in (9, 10) else 1.0)  # sezon öncesi stok


def ay_kaydi(ay: date) -> AyKaydi:
    """Bir ayın iş hacmi — saf formül, ay indeksinden."""
    i = _ay_indeksi(ay)
    satis_net = _satis_net(i)
    alis_net = _alis_net(i)

    # Tahsilat ortalama 2 ay sonra gelir; ilk aylarda devir alacağı tahsil edilir.
    tahsilat = _satis_net(i - 2) * (1 + KDV_ORAN) * _TAHSILAT_ORANI
    satici_odeme = _alis_net(i - 1) * (1 + KDV_ORAN) * _ODEME_ORANI

    return AyKaydi(
        ay=ay,
        satis_net=satis_net,
        alis_net=alis_net,
        personel=satis_net * _PERSONEL_ORANI,
        genel_gider=satis_net * _GENEL_ORANI * (1.18 if ay.month == 12 else 1.0),
        amortisman=96_500.0,
        faiz=_kredi_faizi(i),
        tahsilat=tahsilat,
        satici_odeme=satici_odeme,
        # Beyan bir ay sonra ödenir: bu ayın çıkışı geçen ayın KDV'sidir (kural: KDV
        # gider değil finansman yükü — bkz. CLAUDE.md «KDV NAKİT KÖPRÜSÜ»).
        vergi_odeme=(max(0.0, (_satis_net(i - 1) - _alis_net(i - 1)) * KDV_ORAN)
                     + satis_net * _KURUMLAR_ORANI),
        sgk_odeme=satis_net * _SGK_ORANI,
        kredi_kullanim=2_400_000.0 if (i % 12 == 3) else 0.0,
        kredi_odeme=_kredi_anapara_taksiti(i),
    )


def _aydan(i: int) -> date:
    yil = ILK_AY.year + (ILK_AY.month - 1 + i) // 12
    ay = ((ILK_AY.month - 1 + i) % 12) + 1
    return date(yil, ay, 1)


def _kredi_anapara_taksiti(i: int) -> float:
    """İki krediden gelen aylık anapara — biri baştan, biri 16. aydan itibaren."""
    taksit = 118_000.0
    if i >= 16:
        taksit += 96_000.0
    return taksit


def _kredi_faizi(i: int) -> float:
    kalan = max(0.0, 6_800_000.0 - 118_000.0 * i) + (2_400_000.0 if i >= 16 else 0.0)
    return kalan * 0.0335


def aylar(bas: str, bit: str) -> list[AyKaydi]:
    """Seçili aralıkla KESİŞEN aylar — kural 1: aralık dışına çıkılmaz."""
    b, s = _tarih(bas), _tarih(bit)
    out: list[AyKaydi] = []
    ay = date(max(b, ILK_AY).year, max(b, ILK_AY).month, 1)
    son = min(s, date(SON_AY.year, SON_AY.month, 28))
    while ay <= son:
        out.append(ay_kaydi(ay))
        ay = _aydan(_ay_indeksi(ay) + 1)
    return out


def _tarih(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def gun_sayisi(bas: str, bit: str) -> int:
    return max(1, (_tarih(bit) - _tarih(bas)).days + 1)


# --------------------------------------------------------------------- cariler
# Ünvanlar kurgudur; gerçek bir müşteri adı mağaza sayfasına DÜŞMEZ (kural 7'nin
# ruhu: dışarı çıkan her şey bilerek çıkar).
MUSTERILER: tuple[tuple[str, str, int, float], ...] = (
    # (kod, ünvan, vade günü, ciro payı)
    ("120.01.0001", "AYDIN MAKİNA SANAYİ LTD. ŞTİ.", 90, 0.148),
    ("120.01.0002", "DEMİRHAN İNŞAAT TAAHHÜT A.Ş.", 120, 0.121),
    ("120.01.0003", "KARADENİZ OTOMOTİV TİCARET LTD.", 60, 0.104),
    ("120.01.0004", "EGE PLASTİK KALIP SAN. A.Ş.", 90, 0.093),
    ("120.01.0005", "BOZKURT ELEKTRİK MALZ. LTD. ŞTİ.", 45, 0.081),
    ("120.01.0006", "ANADOLU SOĞUTMA SİSTEMLERİ A.Ş.", 75, 0.074),
    ("120.01.0007", "SELİMOĞLU METAL İŞLEME LTD.", 120, 0.068),
    ("120.01.0008", "MARMARA TEKNİK HIRDAVAT A.Ş.", 30, 0.061),
    ("120.01.0009", "YILDIZ TARIM MAKİNALARI LTD. ŞTİ.", 90, 0.055),
    ("120.01.0010", "ÇUKUROVA ENDÜSTRİYEL TESİS A.Ş.", 60, 0.049),
    ("120.01.0011", "TOROS BORU PROFİL SANAYİ LTD.", 45, 0.042),
    ("120.01.0012", "GÜNEY MERMER MADENCİLİK A.Ş.", 150, 0.038),
    ("120.01.0013", "KAPADOKYA GIDA LOJİSTİK LTD. ŞTİ.", 30, 0.034),
    ("120.01.0014", "TRAKYA AMBALAJ BASKI SAN. A.Ş.", 60, 0.032),
)

SATICILAR: tuple[tuple[str, str, int, float], ...] = (
    ("320.01.0001", "ÖZTÜRK ÇELİK HADDE SANAYİ A.Ş.", 60, 0.231),
    ("320.01.0002", "BATI RULMAN İTHALAT LTD. ŞTİ.", 90, 0.174),
    ("320.01.0003", "NUR KİMYA BOYA SANAYİ A.Ş.", 45, 0.139),
    ("320.01.0004", "ERCAN ELEKTRİK MOTOR LTD.", 30, 0.112),
    ("320.01.0005", "SAMSUN DÖKÜM MAKİNA A.Ş.", 75, 0.098),
    ("320.01.0006", "AKDENİZ AMBALAJ SANAYİ LTD. ŞTİ.", 60, 0.086),
    ("320.01.0007", "İZMİR HİDROLİK PNÖMATİK A.Ş.", 45, 0.067),
    ("320.01.0008", "KONYA VİDA BAĞLANTI ELEM. LTD.", 30, 0.053),
    ("320.01.0009", "BURSA NAKLİYAT LOJİSTİK A.Ş.", 15, 0.040),
)

# Banka hesapları: ikisi mevduat, biri kredi. `ban_hesap_tip` canlıda kredi
# hesaplarında da 1 DEĞİL (bkz. CLAUDE.md «kredi_banka_mi»); demo bu tuzağı
# bilerek taşır ki kredi hesabının 300 önekinden tanınması sınanabilsin.
BANKALAR: tuple[tuple[str, str, str, int], ...] = (
    ("BNK01", "VAKIF BANKASI — TİCARİ MEVDUAT", "102.01.001", 0),
    ("BNK02", "ZİRAAT BANKASI — VADESİZ TL", "102.01.002", 0),
    ("BNK03", "GARANTİ — SPOT KREDİ HESABI", "300.02.001", 0),
)


def musteri_bakiye(m: tuple[str, str, int, float], asof: str) -> float:
    """Bir müşterinin açık bakiyesi — son ~2,5 ayın brüt satışından payına düşen."""
    son = _son_aylar(asof, 3)
    if not son:
        return 0.0
    taban = son[-1].satis_brut * 1.0 + son[-2].satis_brut * 0.72 + son[-3].satis_brut * 0.34
    return taban * m[3]


def satici_bakiye(s: tuple[str, str, int, float], asof: str) -> float:
    son = _son_aylar(asof, 2)
    if not son:
        return 0.0
    taban = son[-1].alis_brut * 1.0 + son[-2].alis_brut * 0.58
    return taban * s[3]


def _son_aylar(asof: str, adet: int) -> list[AyKaydi]:
    i = _ay_indeksi(_tarih(asof).replace(day=1))
    i = max(0, min(i, _ay_indeksi(SON_AY)))
    return [ay_kaydi(_aydan(max(0, i - k))) for k in range(adet - 1, -1, -1)]


def kumulatif(asof: str) -> dict[str, float]:
    """
    Defterin başından `asof`a kadar birikmiş NET bakiyeler (TDHP).

    Pozitif = borç bakiyesi (varlık), negatif = alacak bakiyesi (kaynak).
    Bilanço bu satırlardan kurulur; denge burada garanti edilir (570 tamponu).
    """
    ayl = aylar(ILK_AY.isoformat(), asof)
    satis = sum(a.satis_net for a in ayl)
    alis = sum(a.alis_net for a in ayl)
    smm = sum(a.smm for a in ayl)
    personel = sum(a.personel for a in ayl)
    genel = sum(a.genel_gider for a in ayl)
    amort = sum(a.amortisman for a in ayl)
    faiz = sum(a.faiz for a in ayl)
    nakit = ACILIS_NAKIT + sum(a.nakit_giris - a.nakit_cikis for a in ayl)

    alacak = sum(musteri_bakiye(m, asof) for m in MUSTERILER)
    borc = sum(satici_bakiye(s, asof) for s in SATICILAR)
    stok = alis - smm + 2_450_000.0
    hes_kdv = satis * KDV_ORAN
    ind_kdv = alis * KDV_ORAN
    kdv_net = max(0.0, hes_kdv - ind_kdv)
    kredi_kalan = max(0.0, 6_800_000.0 + sum(a.kredi_kullanim - a.kredi_odeme for a in ayl))

    kasa = 96_400.0
    banka = nakit - kasa
    demirbas = 14_900_000.0
    birikmis_amort = -(3_100_000.0 + amort)

    # Dönem hesapları (6xx/7xx) — bilanço motoru dönem kârını bunlardan çıkarır.
    donem = {
        "600": -satis,
        "621": smm,
        "632": personel + genel,
        "770": amort,
        "780": faiz,
    }

    varliklar = {
        "100": kasa,
        "102": banka,
        "120": alacak,
        "153": stok,
        "191": ind_kdv * 0.11,      # devreden indirilecek KDV
        "252": demirbas,
        "257": birikmis_amort,
    }
    kaynaklar = {
        "300": -kredi_kalan,
        "320": -borc,
        "360": -(kdv_net * 0.34 + 96_000.0),
        "361": -158_000.0,
        "391": -hes_kdv * 0.09,
        "500": -SERMAYE,
    }
    toplam = sum(varliklar.values()) + sum(kaynaklar.values()) + sum(donem.values())
    kaynaklar["570"] = -toplam   # geçmiş yıl kârları: dengeyi kuran tampon

    return {**varliklar, **kaynaklar, **donem}


def gun_dagit(toplam: float, bas: str, bit: str, adet: int) -> list[tuple[date, float]]:
    """
    Bir dönem toplamını `adet` fişe böler — TOPLAMI KORUYARAK.

    Detay penceresi (kural 3c) kendi toplamını panel toplamıyla kıyaslar ve
    tutmazsa ekranda söyler. Yuvarlama farkı son fişe yazılır ki demo, olmayan bir
    tutarsızlığı varmış gibi göstermesin.
    """
    b, s = _tarih(bas), _tarih(bit)
    gun = max(1, (s - b).days)
    adet = max(1, adet)
    paylar = [0.62 + 0.76 * ((k * 7 % 11) / 10.0) for k in range(adet)]
    olcek = toplam / sum(paylar) if sum(paylar) else 0.0
    out: list[tuple[date, float]] = []
    kalan = toplam
    for k, p in enumerate(paylar):
        tutar = round(p * olcek, 2) if k < adet - 1 else round(kalan, 2)
        kalan -= tutar
        out.append((b + timedelta(days=(k * 13 + 3) % gun), tutar))
    return out
