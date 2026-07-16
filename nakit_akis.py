"""
Nakit Akış motoru — banka + kasa fiili hareketlerinden, resmi GL'ye dokunmadan.

Her banka/kasa hareketinin karşı tarafı (aynı evrak no'lu cari satır) kod önekiyle kategorize
edilir: 120/121 müşteri, 320 satıcı, 300/400 + kredi hesabı kredi, 360/368/391 vergi, 361 SGK,
335 personel, 331 ortak, 7xx gider. cha_tip yönü verir (0=giriş, 1=çıkış). NAKİT HESAP = kasa +
normal banka; KREDİ hesabı (ban_hesap_tip=1) nakit sayılmaz → ona giden/gelen para kredi
ödemesi/kullanımıdır (iç transfer değil). Nakit↔nakit iç transferleri elenir.

Açılış nakit, devir (yıl açılış) tarihlemesinden bağımsız olsun diye kapanış − dönem nakit
deltası olarak hesaplanır (her zaman doğru reconcile eder).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ortak import csv_sayi
from ortak import to_float as _f
from ortak import to_int as _i

# Karşı taraf kod öneki (3 hane) → kategori. 'KRD' = kredi hesabı sentinel'i (fetch'ten gelir).
_PREFIX_KATEGORI = {
    "120": "musteri", "121": "musteri",
    "320": "satici", "321": "satici", "329": "satici",
    "300": "kredi", "303": "kredi", "304": "kredi", "305": "kredi", "308": "kredi",
    "309": "kredi", "400": "kredi", "403": "kredi", "KRD": "kredi",
    "360": "vergi", "368": "vergi", "391": "vergi", "393": "vergi", "360.": "vergi",
    "361": "sgk",
    "335": "personel",
    "331": "ortak",
    "770": "gider", "760": "gider", "740": "gider", "730": "gider", "750": "gider",
}

GIRIS_SIRA = ("musteri", "kredi", "ortak", "satici", "vergi", "sgk", "personel", "gider", "diger")
CIKIS_SIRA = ("satici", "kredi", "personel", "sgk", "vergi", "ortak", "gider", "musteri", "diger")
GIRIS_ETIKET = {
    "musteri": "Müşteri tahsilatı", "kredi": "Kredi kullanımı", "ortak": "Ortaklardan giriş",
    "satici": "Satıcıdan iade", "vergi": "Vergi iadesi", "sgk": "SGK iadesi",
    "personel": "Personelden", "gider": "Gider iadesi", "diger": "Diğer girişler",
}
CIKIS_ETIKET = {
    "satici": "Satıcı ödemesi", "kredi": "Kredi ödemesi", "personel": "Personel / Maaş",
    "sgk": "SGK", "vergi": "Vergi", "ortak": "Ortaklar", "gider": "Genel giderler",
    "musteri": "Müşteriye iade", "diger": "Diğer çıkışlar",
}


def _kategori(prefix: str) -> str:
    p = str(prefix or "").strip()
    return _PREFIX_KATEGORI.get(p, _PREFIX_KATEGORI.get(p[:3], "diger"))


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
    donem_delta: float = 0.0
    toplam_giris: float = 0.0
    toplam_cikis: float = 0.0
    giris_kategori: dict = field(default_factory=dict)
    cikis_kategori: dict = field(default_factory=dict)
    diger_giris_kirilim: list = field(default_factory=list)  # [(prefix, tutar), ...]
    diger_cikis_kirilim: list = field(default_factory=list)
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
        """Dönem deltası − kategorize net akış. ~0 olmalı; kapsam dışı hareket işareti."""
        return self.donem_delta - self.net_akis

    @property
    def kredi_net(self) -> float:
        return self.kredi_kullanim - self.kredi_odeme


def _nakit_bakiye(bakiye_rows: list[dict] | None) -> float:
    """fetch_cari_bakiye satırlarından banka+kasa nakit mevcudu (kredi bankaları hariç)."""
    total = 0.0
    for r in (bakiye_rows or []):
        cins = _i(r.get("cins", r.get("CINS")))
        if cins not in (2, 4):
            continue
        if cins == 2 and _i(r.get("ban_hesap_tip", r.get("BAN_HESAP_TIP"))) == 1:
            continue
        total += _f(r.get("borc_h", r.get("BORC_H"))) - _f(r.get("alacak_h", r.get("ALACAK_H")))
    return total


def build_nakit_akis(
    hareket_rows: list[dict] | None = None,
    *,
    bakiye_kapanis_rows: list[dict] | None = None,
    kapanis_nakit: float | None = None,
    donem_delta: float | None = None,
    bas: str = "",
    bit: str = "",
    top_diger: int = 6,
) -> NakitAkis:
    """Banka/kasa hareketleri + kapanış bakiyesi + dönem deltasından Nakit Akış modelini kurar."""
    na = NakitAkis(bas=bas, bit=bit)
    na.kapanis_nakit = kapanis_nakit if kapanis_nakit is not None else _nakit_bakiye(bakiye_kapanis_rows)

    giris: dict[str, float] = defaultdict(float)
    cikis: dict[str, float] = defaultdict(float)
    diger_g: dict[str, float] = defaultdict(float)
    diger_c: dict[str, float] = defaultdict(float)
    aylar: dict[str, AyNakit] = {}
    for r in (hareket_rows or []):
        tip = _i(r.get("tip", r.get("TIP")))
        tutar = abs(_f(r.get("tutar", r.get("TUTAR"))))
        if tutar < 0.005:
            continue
        prefix = str(r.get("prefix", r.get("PREFIX")) or "")
        kat = _kategori(prefix)
        ay = str(r.get("ay", r.get("AY")) or "")
        na.hareket_sayisi += 1
        a = aylar.get(ay)
        if a is None:
            a = aylar[ay] = AyNakit(ay=ay)
        if tip == 0:
            giris[kat] += tutar
            na.toplam_giris += tutar
            a.giris += tutar
            if kat == "kredi":
                na.kredi_kullanim += tutar
            elif kat == "diger":
                diger_g[prefix or "?"] += tutar
        else:
            cikis[kat] += tutar
            na.toplam_cikis += tutar
            a.cikis += tutar
            if kat == "kredi":
                na.kredi_odeme += tutar
            elif kat == "diger":
                diger_c[prefix or "?"] += tutar

    na.giris_kategori = {GIRIS_ETIKET[k]: giris[k] for k in GIRIS_SIRA if giris.get(k, 0.0) > 0.005}
    na.cikis_kategori = {CIKIS_ETIKET[k]: cikis[k] for k in CIKIS_SIRA if cikis.get(k, 0.0) > 0.005}
    na.diger_giris_kirilim = sorted(diger_g.items(), key=lambda x: x[1], reverse=True)[:top_diger]
    na.diger_cikis_kirilim = sorted(diger_c.items(), key=lambda x: x[1], reverse=True)[:top_diger]
    na.aylik = [aylar[k] for k in sorted(aylar)]

    na.donem_delta = donem_delta if donem_delta is not None else na.net_akis
    na.acilis_nakit = na.kapanis_nakit - na.donem_delta
    return na


def nakit_akis_csv(na: NakitAkis) -> str:
    """Nakit Akış özetini CSV'ye çevirir (; ayraç, Türkçe ondalık — TR Excel uyumlu)."""
    s = csv_sayi

    out = ["Bölüm;Kalem;Tutar (TL)"]
    out.append(f"DÖNEM;{na.bas} - {na.bit};")
    out.append(f"ÖZET;Açılış Nakit;{s(na.acilis_nakit)}")
    out.append(f"ÖZET;Toplam Giriş;{s(na.toplam_giris)}")
    out.append(f"ÖZET;Toplam Çıkış;{s(na.toplam_cikis)}")
    out.append(f"ÖZET;Net Nakit Akışı;{s(na.net_akis)}")
    out.append(f"ÖZET;Kapanış Nakit;{s(na.kapanis_nakit)}")
    for etiket, tutar in na.giris_kategori.items():
        out.append(f"GİRİŞLER;{etiket};{s(tutar)}")
    for prefix, tutar in na.diger_giris_kirilim:
        out.append(f"GİRİŞLER (diğer kırılım);{prefix};{s(tutar)}")
    for etiket, tutar in na.cikis_kategori.items():
        out.append(f"ÇIKIŞLAR;{etiket};{s(tutar)}")
    for prefix, tutar in na.diger_cikis_kirilim:
        out.append(f"ÇIKIŞLAR (diğer kırılım);{prefix};{s(tutar)}")
    out.append(f"KREDİ;Kredi Kullanımı;{s(na.kredi_kullanim)}")
    out.append(f"KREDİ;Kredi Ödemesi;{s(na.kredi_odeme)}")
    out.append(f"KREDİ;Net Kredi;{s(na.kredi_net)}")
    for a in na.aylik:
        out.append(f"AYLIK;{a.ay} giriş;{s(a.giris)}")
        out.append(f"AYLIK;{a.ay} çıkış;{s(a.cikis)}")
        out.append(f"AYLIK;{a.ay} net;{s(a.net)}")
    return "\r\n".join(out)
