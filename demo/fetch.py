"""
`infra.mikro_fetch` fonksiyonlarının demo karşılıkları.

İMZALAR BİREBİR AYNIDIR — `test_demo.TestImzaUyumu` bunu sınar. Gerçek fonksiyonun
imzası değişip demonunki geride kalırsa demo, uygulamanın koştuğu yolu artık
koşturmuyor demektir; sessizce yanlış ekran görüntüsü üretmek yerine test kırılır.

`client` parametresi bilerek KULLANILMAZ: demoda ağ yoktur, yil_client sahte bir
nesne döndürür. Parametre yalnız imza uyumu için durur.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from demo import defter
from demo.defter import (
    BANKALAR,
    FIRMA_ADI,
    KDV_ORAN,
    MUSTERILER,
    SATICILAR,
    ay_kaydi,
    aylar,
    kumulatif,
)

# Stok hareket kodları — domain/gercek_durum.py ile aynı (orada sabit olarak yazılı).
SATIS_TIP, ALIS_TIP = 1, 0
EV_SATIS_IRSALIYE, EV_SATIS_FATURA, EV_ALIS_FATURA, EV_ALIS_IRSALIYE = 1, 4, 3, 12


def _t(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


# ------------------------------------------------------------------ künye
def fetch_firma_adi(client: Any) -> str:
    return FIRMA_ADI


# ------------------------------------------------------------------ mizan / GT
def fetch_mizan(client: Any, asof: str) -> list[dict[str, Any]]:
    """
    Kümülatif mizan. Satırlar borç/alacak TOPLAMI taşır, net değil.

    Net doğru olduğu sürece denge de doğrudur (Σborç − Σalacak = Σnet = 0), o yüzden
    her hesaba gerçekçi bir hareket hacmi eklenip aynısı karşı tarafa yazılır.
    """
    out: list[dict[str, Any]] = []
    for kod, net in sorted(kumulatif(asof).items()):
        hacim = abs(net) * 0.42
        out.append({
            "hesap_kodu": kod,
            "borc": round(max(net, 0.0) + hacim, 2),
            "alacak": round(max(-net, 0.0) + hacim, 2),
        })
    return out


def fetch_gelir_tablosu(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    """Dönem 6xx/7xx hareketleri — aralık dışına ÇIKMAZ (kural 1)."""
    ayl = aylar(bas, bit)
    satis = sum(a.satis_net for a in ayl)
    smm = sum(a.smm for a in ayl)
    personel = sum(a.personel for a in ayl)
    genel = sum(a.genel_gider for a in ayl)
    amort = sum(a.amortisman for a in ayl)
    faiz = sum(a.faiz for a in ayl)
    return [
        {"hesap_kodu": "600", "borc": 0.0, "alacak": round(satis * 0.94, 2)},
        {"hesap_kodu": "601", "borc": 0.0, "alacak": round(satis * 0.06, 2)},
        {"hesap_kodu": "610", "borc": round(satis * 0.021, 2), "alacak": 0.0},
        {"hesap_kodu": "621", "borc": round(smm, 2), "alacak": 0.0},
        {"hesap_kodu": "631", "borc": round(personel * 0.34, 2), "alacak": 0.0},
        {"hesap_kodu": "632", "borc": round(personel * 0.66 + genel, 2), "alacak": 0.0},
        {"hesap_kodu": "642", "borc": 0.0, "alacak": round(faiz * 0.11, 2)},
        {"hesap_kodu": "660", "borc": round(faiz, 2), "alacak": 0.0},
        {"hesap_kodu": "770", "borc": round(amort, 2), "alacak": 0.0},
    ]


# ------------------------------------------------------------------ stok
def fetch_stok_ozet(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    """Depodan geçen mal — tip/evraktip kırılımında toplanmış."""
    ayl = aylar(bas, bit)
    satis = sum(a.satis_net for a in ayl)
    alis = sum(a.alis_net for a in ayl)
    n = max(1, len(ayl))
    return [
        {"sth_tip": SATIS_TIP, "sth_evraktip": EV_SATIS_FATURA, "adet": 214 * n,
         "miktar": round(satis / 1420.0, 2), "tutar": round(satis * 0.83, 2),
         "aykiri_adet": 0, "aykiri_tutar": 0.0},
        {"sth_tip": SATIS_TIP, "sth_evraktip": EV_SATIS_IRSALIYE, "adet": 57 * n,
         "miktar": round(satis * 0.17 / 1420.0, 2), "tutar": round(satis * 0.17, 2),
         "aykiri_adet": 0, "aykiri_tutar": 0.0},
        {"sth_tip": ALIS_TIP, "sth_evraktip": EV_ALIS_FATURA, "adet": 96 * n,
         "miktar": round(alis / 1180.0, 2), "tutar": round(alis * 0.89, 2),
         "aykiri_adet": 0, "aykiri_tutar": 0.0},
        {"sth_tip": ALIS_TIP, "sth_evraktip": EV_ALIS_IRSALIYE, "adet": 18 * n,
         "miktar": round(alis * 0.11 / 1180.0, 2), "tutar": round(alis * 0.11, 2),
         "aykiri_adet": 0, "aykiri_tutar": 0.0},
    ]


def fetch_stok_aylik(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    return [{"ay": a.etiket, "tutar": round(a.satis_net, 2)} for a in aylar(bas, bit)]


# ------------------------------------------------------------------ cari
def _cari_satir(kod: str, unvan: str, musteri: bool) -> dict[str, Any]:
    return {
        "kod": kod,
        "unvan": unvan,
        "muh_kod": "120.01" if musteri else "320.01",
        "hareket_tipi": 1 if musteri else 2,
        "baglanti_tipi": 0 if musteri else 1,
    }


def fetch_acik_kalemler(client: Any, asof: str, bas: str, bit: str) -> list[dict[str, Any]]:
    """
    Açık kalemler + dönem hareketi.

    `tip` yön taşır: müşteride 0 = fatura (borç doğuran), 1 = tahsilat. Satıcıda
    tersi. Yaşlandırma FIFO ile en eski faturayı kapatır, o yüzden hem faturalar
    hem ödemeler üretilir — yalnız fatura üretmek DSO'yu sonsuz gösterirdi.
    """
    son = _t(asof)
    out: list[dict[str, Any]] = []
    for grup, musteri in ((MUSTERILER, True), (SATICILAR, False)):
        for kod, unvan, vade_gun, pay in grup:
            temel = _cari_satir(kod, unvan, musteri)
            for geri in range(0, 6):
                ay_basi = (son.replace(day=1) - timedelta(days=1 + 30 * geri)).replace(day=1)
                if ay_basi < defter.ILK_AY:
                    continue
                k = ay_kaydi(ay_basi)
                tutar = (k.satis_brut if musteri else k.alis_brut) * pay
                evrak = min(son, ay_basi + timedelta(days=13))
                vade = evrak + timedelta(days=vade_gun)
                out.append({**temel, "tip": 0 if musteri else 1,
                            "tutar": round(tutar, 2),
                            "tutar_donem": round(tutar, 2) if _t(bas) <= evrak <= _t(bit) else 0.0,
                            "evrak_tarihi": evrak.isoformat(),
                            "cha_vade": vade.isoformat()})
                # Eski faturaların tahsilatı/ödemesi — açık kalan son iki aydır.
                if geri >= 2:
                    ode = evrak + timedelta(days=min(vade_gun, 55))
                    if ode <= son:
                        out.append({**temel, "tip": 1 if musteri else 0,
                                    "tutar": round(tutar * 0.96, 2),
                                    "tutar_donem": round(tutar * 0.96, 2) if _t(bas) <= ode <= _t(bit) else 0.0,
                                    "evrak_tarihi": ode.isoformat(),
                                    "cha_vade": ode.isoformat()})
    return out


def fetch_cari_vade_gun(client: Any) -> dict[str, int]:
    return {kod: vade for kod, _unvan, vade, _pay in (*MUSTERILER, *SATICILAR)}


def fetch_cari_bakiye(client: Any, asof: str) -> list[dict[str, Any]]:
    """Cari + banka bakiyeleri. Banka satırları `ban_muh_kod` ile TDHP'ye bağlanır."""
    out: list[dict[str, Any]] = []
    for kod, unvan, _vade, pay in MUSTERILER:
        b = defter.musteri_bakiye((kod, unvan, 0, pay), asof)
        out.append({"kod": kod, "cari_muh_kod": "120.01", "ban_muh_kod": "",
                    "ban_hesap_tip": None, "ban_ismi": "", "cins": 0,
                    "hareket_tipi": 1, "baglanti_tipi": 0,
                    "borc_h": round(b * 1.6, 2), "alacak_h": round(b * 0.6, 2)})
    for kod, unvan, _vade, pay in SATICILAR:
        b = defter.satici_bakiye((kod, unvan, 0, pay), asof)
        out.append({"kod": kod, "cari_muh_kod": "320.01", "ban_muh_kod": "",
                    "ban_hesap_tip": None, "ban_ismi": "", "cins": 0,
                    "hareket_tipi": 2, "baglanti_tipi": 1,
                    "borc_h": round(b * 0.55, 2), "alacak_h": round(b * 1.55, 2)})
    kum = kumulatif(asof)
    banka_toplam = kum["102"]
    for i, (kod, ad, muh, tip) in enumerate(BANKALAR):
        kredi = muh.startswith("300")
        bakiye = -kum["300"] if kredi else banka_toplam * (0.62 if i == 0 else 0.38)
        out.append({"kod": kod, "cari_muh_kod": "", "ban_muh_kod": muh,
                    "ban_hesap_tip": tip, "ban_ismi": ad, "cins": 1,
                    "hareket_tipi": 0, "baglanti_tipi": 2,
                    "borc_h": 0.0 if kredi else round(bakiye, 2),
                    "alacak_h": round(bakiye, 2) if kredi else 0.0})
    return out


def fetch_bakiye_ozet(client: Any, asof: str) -> list[dict[str, Any]]:
    kum = kumulatif(asof)
    return [{"ana": ana, "bakiye": round(kum.get(ana, 0.0), 2)}
            for ana in ("100", "102", "120", "153", "191", "300", "320", "360", "361", "391")]


# ------------------------------------------------------------------ nakit
# Karşı hesap öneki → (tip, ay tutarı). tip: 0 giriş, 1 çıkış (domain/nakit_akis.py).
def _nakit_kalemleri(a: defter.AyKaydi) -> list[tuple[str, int, float]]:
    return [
        ("120", 0, a.tahsilat),
        ("300", 0, a.kredi_kullanim),
        ("320", 1, a.satici_odeme),
        ("335", 1, a.personel),
        ("360", 1, a.vergi_odeme),
        ("361", 1, a.sgk_odeme),
        ("770", 1, a.genel_gider),
        ("300", 1, a.kredi_odeme),
        ("780", 1, a.faiz),
    ]


# Bir ayın bir kategorisi kaç fişe bölünür. Ekranda «9 hareket» yazan bir panel
# rakamın tek bir işlem sanılmasına yol açıyordu (kural 3c: hareket sayısı, rakamın
# dönem toplamı olduğunu sorulmadan söyler); ay başına dört fiş gerçekçi görünüyor.
FIS_BOLME = 4


def fetch_nakit_akis_gl(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in aylar(bas, bit):
        ay_bas, ay_bit = _ay_araligi(a, bas, bit)
        if ay_bit < ay_bas:
            continue
        for prefix, tip, tutar in _nakit_kalemleri(a):
            if tutar <= 0:
                continue
            for _gun, pay in defter.gun_dagit(tutar, ay_bas.isoformat(), ay_bit.isoformat(),
                                              FIS_BOLME):
                out.append({"ay": a.etiket, "prefix": prefix, "tip": tip, "tutar": round(pay, 2)})
    return out


def _ay_araligi(a: defter.AyKaydi, bas: str, bit: str) -> tuple[date, date]:
    """Ayın seçili aralıkla kesişimi — kural 1: aralık dışına taşan gün üretilmez."""
    ay_son = (a.ay + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return max(_t(bas), a.ay), min(_t(bit), ay_son)


def fetch_nakit_akis_detay(client: Any, bas: str, bit: str, tip: int,
                           adet: int = 2000) -> list[dict[str, Any]]:
    """
    Bir kategorinin arkasındaki fişler (kural 3c).

    Fiş toplamı özet toplamına EŞİT olmak zorunda: pencere ikisini kıyaslıyor ve
    tutmazsa ekranda söylüyor. Bölme `gun_dagit` ile toplamı koruyarak yapılır.
    """
    out: list[dict[str, Any]] = []
    yevmiye = 4100
    for a in aylar(bas, bit):
        ay_bas, ay_bit = _ay_araligi(a, bas, bit)
        if ay_bit < ay_bas:
            continue
        for prefix, kalem_tip, tutar in _nakit_kalemleri(a):
            if kalem_tip != tip or tutar <= 0:
                continue
            for gun, pay in defter.gun_dagit(tutar, ay_bas.isoformat(), ay_bit.isoformat(), FIS_BOLME):
                yevmiye += 1
                out.append({"tarih": gun.isoformat(), "yevmiye": yevmiye,
                            "hesap": f"{prefix}.01.001", "prefix": prefix,
                            "tutar": round(pay, 2)})
    return out[:adet]


def _giris_cikis(bas: str, bit: str) -> tuple[float, float]:
    ayl = aylar(bas, bit)
    return sum(a.nakit_giris for a in ayl), sum(a.nakit_cikis for a in ayl)


def fetch_nakit_ozet_ve_aylik(client: Any, bas: str,
                              bit: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    giren, cikan = _giris_cikis(bas, bit)
    ozet = [{"giren": round(giren, 2), "cikan": round(cikan, 2)}]
    aylik = [{"ay": a.etiket, "giren": round(a.nakit_giris, 2), "cikan": round(a.nakit_cikis, 2)}
             for a in aylar(bas, bit)]
    return ozet, aylik


def fetch_nakit_akis_hareket(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    """Cari yolu — GL yerine banka hareketinden nakit akış (kurulum ayarına bağlı)."""
    out: list[dict[str, Any]] = []
    for a in aylar(bas, bit):
        for prefix, tip, tutar in _nakit_kalemleri(a):
            if tutar <= 0:
                continue
            out.append({"ay": a.etiket, "prefix": prefix, "tip": tip, "tutar": round(tutar, 2),
                        "kcins": 1, "kkredi": 1 if prefix == "300" else 0, "kprefix": prefix})
    return out


def fetch_nakit_bakiye_gl(client: Any, asof: str) -> float:
    kum = kumulatif(asof)
    return round(kum["100"] + kum["102"], 2)


def fetch_nakit_delta_gl(client: Any, bas: str, bit: str) -> float:
    giren, cikan = _giris_cikis(bas, bit)
    return round(giren - cikan, 2)


def fetch_nakit_delta(client: Any, bas: str, bit: str) -> float:
    return fetch_nakit_delta_gl(client, bas, bit)


# ------------------------------------------------------------------ KDV
def fetch_kdv_ozet(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in aylar(bas, bit):
        out.append({"ay": a.etiket, "hesap": "391", "borc": 0.0,
                    "alacak": round(a.satis_net * KDV_ORAN, 2)})
        out.append({"ay": a.etiket, "hesap": "191",
                    "borc": round(a.alis_net * KDV_ORAN, 2), "alacak": 0.0})
    return out


# ------------------------------------------------------------------ kredi
def fetch_kredi_anapara(client: Any, bas: str, bit: str) -> float:
    return round(sum(a.kredi_odeme for a in aylar(bas, bit)), 2)


def fetch_kredi_gl(client: Any, bas: str, bit: str) -> dict[str, float]:
    ayl = aylar(bas, bit)
    return {"kullanim": round(sum(a.kredi_kullanim for a in ayl), 2),
            "odeme": round(sum(a.kredi_odeme for a in ayl), 2)}


def fetch_kredi_odemeleri_gl(client: Any, bas: str, bit: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in aylar(bas, bit):
        if a.kredi_odeme <= 0:
            continue
        ay_bit = (a.ay + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        for gun, pay in defter.gun_dagit(a.kredi_odeme, max(_t(bas), a.ay).isoformat(),
                                         min(_t(bit), ay_bit).isoformat(), 2):
            out.append({"tarih": gun.isoformat(), "hesap": "300.02.001",
                        "hesap_ad": "GARANTİ — SPOT KREDİ HESABI", "tutar": round(pay, 2),
                        "pay": 1.0, "banka_kredisi": 1, "kredi_karti": 0})
    return out


def fetch_kredi_taksitleri(client: Any, *, ay_ileri: int = 24,
                           asof: str = "") -> list[dict[str, Any]]:
    """İleriye dönük taksit takvimi — Tahmin sekmesinin kredi ayağı."""
    bas = _t(asof) if asof else date.today()
    out: list[dict[str, Any]] = []
    for k in range(ay_ileri):
        ay = (bas.replace(day=1) + timedelta(days=32 * k)).replace(day=1)
        kalan_ay = max(0, 46 - k)
        if kalan_ay == 0:
            break
        anapara = 118_000.0 + (96_000.0 if k < 30 else 0.0)
        faiz = anapara * 0.42
        out.append({"ay": f"{ay.year:04d}-{ay.month:02d}",
                    "vade": ay.replace(day=15).isoformat(),
                    "banka": "BNK03", "banka_ad": "GARANTİ — SPOT KREDİ HESABI",
                    "tutar": round(anapara + faiz, 2),
                    "anapara": round(anapara, 2), "faiz": round(faiz, 2)})
    return out


def fetch_kredi_karti_borclari(client: Any, asof: str) -> list[dict[str, Any]]:
    return [{"hesap": "309.01.001", "borc": round(kumulatif(asof)["300"] * -0.06, 2)}]


# ------------------------------------------------------------------ döviz
# Kur burada da VARSAYILMAZ, defterin kendi USD karşılığından ima edilir: kurgu
# firmanın satışı sabit bir kurla değil, yıl yıl değişen kurla dolara çevrilir ki
# «TL'de büyüdük, dolarda küçüldük» tablosu demoda da görünsün (gerçek kurulumlarda
# tam olarak bu görülüyor).
def _kur(ay: date) -> float:
    i = (ay.year - defter.ILK_AY.year) * 12 + (ay.month - defter.ILK_AY.month)
    return 32.4 * (1 + 0.0225 * i)


def fetch_doviz_ozet(client: Any, bas: str, bit: str) -> dict[str, float]:
    ayl = aylar(bas, bit)
    if not ayl:
        return {"satis_tl": 0.0, "satis_usd": 0.0, "kur_ortalama": 0.0, "kur_son": 0.0}
    tl = sum(a.satis_net for a in ayl)
    usd = sum(a.satis_net / _kur(a.ay) for a in ayl)
    return {
        "satis_tl": round(tl, 2),
        "satis_usd": round(usd, 2),
        "kur_ortalama": round(tl / usd, 4) if usd else 0.0,
        "kur_son": round(_kur(ayl[-1].ay), 4),
    }
