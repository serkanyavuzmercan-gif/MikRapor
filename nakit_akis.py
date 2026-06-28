"""
Nakit Akış motoru — banka + kasa fiili hareketlerinden, resmi GL'ye dokunmadan.

Her banka/kasa hareketinin karşı tarafı (aynı evrak no'lu, banka/kasa olmayan cari satır) kod
önekiyle kategorize edilir: 120/121 müşteri tahsilatı, 320 satıcı ödemesi, 300 banka kredisi,
360 vergi/SGK, 335 ortak/personel. cha_tip yönü verir (0=giriş, 1=çıkış). Banka↔banka/kasa iç
transferleri elenir (gerçek nakit hareketi değil). Açılış/kapanış nakit cari bakiyeden alınır.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from gercek_durum import _f, _i

# Karşı taraf kod öneki → kategori anahtarı
_PREFIX_KATEGORI = {
    "120": "musteri", "121": "musteri",
    "320": "satici", "321": "satici", "329": "satici",
    "300": "kredi", "303": "kredi", "304": "kredi", "305": "kredi", "308": "kredi", "309": "kredi",
    "360": "vergi", "361": "vergi", "368": "vergi", "369": "vergi",
    "335": "ortak", "331": "ortak",
}

# Gösterim sırası + etiket (yöne göre ayrı)
GIRIS_SIRA = ("musteri", "kredi", "ortak", "vergi", "satici", "diger")
CIKIS_SIRA = ("satici", "kredi", "vergi", "ortak", "musteri", "diger")
GIRIS_ETIKET = {
    "musteri": "Müşteri tahsilatı", "kredi": "Kredi kullanımı", "ortak": "Ortaklardan giriş",
    "vergi": "Vergi iadesi", "satici": "Satıcıdan iade", "diger": "Diğer girişler",
}
CIKIS_ETIKET = {
    "satici": "Satıcı ödemesi", "kredi": "Kredi ödemesi", "vergi": "Vergi & SGK",
    "ortak": "Personel / Ortaklar", "musteri": "Müşteriye iade", "diger": "Diğer çıkışlar",
}


def _kategori(prefix: str) -> str:
    return _PREFIX_KATEGORI.get(str(prefix or "").strip()[:3], "diger")


@dataclass
class AyNakit:
    """Bir ayın (YYYY-MM) nakit giriş/çıkışı — trend için."""
    ay: str
    giris: float = 0.0
    cikis: float = 0.0

    @property
    def net(self) -> float:
        return self.giris - self.cikis


@dataclass
class NakitAkis:
    bas: str = ""
    bit: str = ""
    acilis_nakit: float = 0.0
    kapanis_nakit: float = 0.0
    toplam_giris: float = 0.0
    toplam_cikis: float = 0.0
    giris_kategori: dict = field(default_factory=dict)   # etiket → tutar
    cikis_kategori: dict = field(default_factory=dict)
    kredi_kullanim: float = 0.0
    kredi_odeme: float = 0.0
    aylik: list = field(default_factory=list)
    hareket_sayisi: int = 0

    @property
    def net_akis(self) -> float:
        return self.toplam_giris - self.toplam_cikis

    @property
    def kapanis_hesaplanan(self) -> float:
        return self.acilis_nakit + self.net_akis

    @property
    def mutabakat_farki(self) -> float:
        """Gerçek kapanış − (açılış + net akış). ~0 olmalı; iç transfer/kur farkı işareti."""
        return self.kapanis_nakit - self.kapanis_hesaplanan

    @property
    def kredi_net(self) -> float:
        """Kredi kullanımı − kredi ödemesi (poz = net borçlanma)."""
        return self.kredi_kullanim - self.kredi_odeme


def _nakit_bakiye(bakiye_rows: list[dict] | None) -> float:
    """fetch_cari_bakiye satırlarından banka+kasa nakit mevcudu (kredi bankaları hariç)."""
    total = 0.0
    for r in (bakiye_rows or []):
        cins = _i(r.get("cins", r.get("CINS")))
        if cins not in (2, 4):
            continue
        if cins == 2 and _i(r.get("ban_hesap_tip", r.get("BAN_HESAP_TIP"))) == 1:
            continue  # kredi hesabı = nakit değil
        total += _f(r.get("borc_h", r.get("BORC_H"))) - _f(r.get("alacak_h", r.get("ALACAK_H")))
    return total


def build_nakit_akis(
    hareket_rows: list[dict] | None = None,
    *,
    bakiye_acilis_rows: list[dict] | None = None,
    bakiye_kapanis_rows: list[dict] | None = None,
    bas: str = "",
    bit: str = "",
) -> NakitAkis:
    """Banka/kasa hareketleri + açılış/kapanış bakiyesinden Nakit Akış modelini kurar."""
    na = NakitAkis(bas=bas, bit=bit)
    na.acilis_nakit = _nakit_bakiye(bakiye_acilis_rows)
    na.kapanis_nakit = _nakit_bakiye(bakiye_kapanis_rows)

    giris: dict[str, float] = defaultdict(float)
    cikis: dict[str, float] = defaultdict(float)
    aylar: dict[str, AyNakit] = {}
    for r in (hareket_rows or []):
        tip = _i(r.get("tip", r.get("TIP")))
        tutar = abs(_f(r.get("tutar", r.get("TUTAR"))))
        if tutar < 0.005:
            continue
        kat = _kategori(str(r.get("prefix", r.get("PREFIX")) or ""))
        ay = str(r.get("ay", r.get("AY")) or "")
        na.hareket_sayisi += 1
        a = aylar.get(ay)
        if a is None:
            a = aylar[ay] = AyNakit(ay=ay)
        if tip == 0:  # giriş (para geldi)
            giris[kat] += tutar
            na.toplam_giris += tutar
            a.giris += tutar
            if kat == "kredi":
                na.kredi_kullanim += tutar
        else:          # çıkış (para gitti)
            cikis[kat] += tutar
            na.toplam_cikis += tutar
            a.cikis += tutar
            if kat == "kredi":
                na.kredi_odeme += tutar

    na.giris_kategori = {
        GIRIS_ETIKET[k]: giris[k] for k in GIRIS_SIRA if giris.get(k, 0.0) > 0.005
    }
    na.cikis_kategori = {
        CIKIS_ETIKET[k]: cikis[k] for k in CIKIS_SIRA if cikis.get(k, 0.0) > 0.005
    }
    na.aylik = [aylar[k] for k in sorted(aylar)]
    return na


def nakit_akis_csv(na: NakitAkis) -> str:
    """Nakit Akış özetini CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    def s(v: float) -> str:
        return f"{v:.2f}".replace(".", ",")

    out = ["Bölüm;Kalem;Tutar (TL)"]
    out.append(f"DÖNEM;{na.bas} - {na.bit};")
    out.append(f"ÖZET;Açılış Nakit;{s(na.acilis_nakit)}")
    out.append(f"ÖZET;Toplam Giriş;{s(na.toplam_giris)}")
    out.append(f"ÖZET;Toplam Çıkış;{s(na.toplam_cikis)}")
    out.append(f"ÖZET;Net Nakit Akışı;{s(na.net_akis)}")
    out.append(f"ÖZET;Kapanış Nakit (gerçek);{s(na.kapanis_nakit)}")
    out.append(f"ÖZET;Kapanış Nakit (hesaplanan);{s(na.kapanis_hesaplanan)}")
    for etiket, tutar in na.giris_kategori.items():
        out.append(f"GİRİŞLER;{etiket};{s(tutar)}")
    for etiket, tutar in na.cikis_kategori.items():
        out.append(f"ÇIKIŞLAR;{etiket};{s(tutar)}")
    out.append(f"KREDİ;Kredi Kullanımı;{s(na.kredi_kullanim)}")
    out.append(f"KREDİ;Kredi Ödemesi;{s(na.kredi_odeme)}")
    out.append(f"KREDİ;Net Kredi;{s(na.kredi_net)}")
    for a in na.aylik:
        out.append(f"AYLIK;{a.ay} giriş;{s(a.giris)}")
        out.append(f"AYLIK;{a.ay} çıkış;{s(a.cikis)}")
        out.append(f"AYLIK;{a.ay} net;{s(a.net)}")
    return "\r\n".join(out)
