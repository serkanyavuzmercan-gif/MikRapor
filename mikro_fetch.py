"""
Mikro API → finansal tablo verisi (genel muhasebe / MUHASEBE_FISLERI).

Üç çekim:
  - fetch_mizan(asof)            → tarih itibarıyla kümülatif mizan (bilanço için)
  - fetch_gelir_tablosu(bas,bit) → dönem 6xx hareketleri (gelir tablosu için)
  - fetch_firma_adi()            → FIRMALAR.fir_unvan

KRİTİK: fis_meblag0 = İŞARETLİ TL tutar (poz=borç, neg=alacak). meblag1=USD (alacak DEĞİL).
Bakiye = SUM(fis_meblag0). Mikro'nun kendi mizanıyla kuruşu kuruşuna doğrulandı.
Bkz. MIKRO-SEMA-NOTLARI.md.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mikro_api import MikroAPIError, MikroClient, get_row_value, parse_sql_rows
from cari_vade import hesapla_vade_gun


def fetch_firma_adi(client: MikroClient) -> str:
    """
    Firma ünvanını Mikro'dan çeker — FIRMALAR.fir_unvan (kolon canlı Mikro'da teyit edildi).

    FIRMALAR kuruluma göre çok firmalı olabilir; önce config'teki firma koduyla eşleştirmeyi
    dener (kod kolonu Mikro sürümüne göre değişebildiği için birkaç aday denenir), eşleşme
    yoksa tek/ilk dolu ünvanı döndürür. Hiç ünvan yoksa boş string döner (sessiz; çağıran
    taraf elle girilen firma adına / boş başlığa düşer).
    """
    def _oku(sql: str) -> str:
        try:
            rows = parse_sql_rows(client.sql_veri_oku(sql, timeout=20, max_attempts=2))
        except MikroAPIError:
            return ""
        if rows:
            v = get_row_value(rows[0], "fir_unvan")
            if v:
                return str(v).strip()
        return ""

    fk = str(client.cfg.firma_kodu or "").strip()
    if fk:
        for kol in ("fir_kod", "fir_no", "fir_firmano", "fir_DBCno", "fir_sirano"):
            ad = _oku(
                f"SELECT TOP 1 fir_unvan FROM FIRMALAR WITH (NOLOCK) "
                f"WHERE [{kol}] = '{fk}' AND fir_unvan IS NOT NULL AND LTRIM(fir_unvan) <> ''"
            )
            if ad:
                return ad
    return _oku(
        "SELECT TOP 1 fir_unvan FROM FIRMALAR WITH (NOLOCK) "
        "WHERE fir_unvan IS NOT NULL AND LTRIM(fir_unvan) <> ''"
    )


def fetch_gelir_tablosu(client: MikroClient, bas: str, bit: str) -> list[dict[str, Any]]:
    """
    Dönem (bas..bit, 'YYYY-MM-DD') için 6xx hesap hareketleri: hesap başına borç/alacak.

    Gelir tablosu bir DÖNEM akışıdır (bilanço gibi kümülatif değil) → tarih aralığı. Bitiş günü
    tam dahil edilsin diye < (bit+1gün).

    YIL SONU KAPANIŞI: gelir/gider hesaplarını dönem sonucuna taşıyan kapanış/aktarım fişleri
    6xx'i sıfırlayıp 690'a (Dönem Kârı/Zararı) aktarır; dönem sonunu (31 Aralık) dahil edince
    kapatılmış yılda tablo sıfırlanır. Bu fişler 690'a dokunur, normal satış/gider fişleri
    dokunmaz → 690'a dokunan yevmiye maddelerini hariç tutarız. Böylece hangi bitiş tarihi
    seçilirse seçilsin gerçek dönem sonucu gelir; yıl sonu maliyet/kur/vergi kayıtları korunur.
    (Yevmiye no güvenilmezse alt sorgu boş döner → eski davranışa zarafetle düşer.)
    """
    try:
        bit_son = (date.fromisoformat(bit) + timedelta(days=1)).isoformat()
    except ValueError:
        bit_son = bit
    kapanis_haric = (
        "AND fis_yevmiye_no NOT IN ("
        "SELECT fis_yevmiye_no FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        "WHERE fis_iptal = 0 AND fis_hesap_kod LIKE '690%' "
        f"AND fis_tarih >= '{bas}' AND fis_tarih < '{bit_son}' "
        "AND fis_yevmiye_no IS NOT NULL AND fis_yevmiye_no <> 0)"
    )
    sql = (
        "SELECT fis_hesap_kod AS hesap_kodu, "
        "SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc, "
        "SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak "
        "FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        "WHERE fis_iptal = 0 AND fis_hesap_kod LIKE '6%' "
        f"AND fis_tarih >= '{bas}' AND fis_tarih < '{bit_son}' "
        f"{kapanis_haric} "
        "GROUP BY fis_hesap_kod"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def _bit_son(bit: str) -> str:
    """Bitiş gününü tam dahil etmek için < (bit+1gün) sınırı (datetime gün-içi saatleri kaçırmasın)."""
    try:
        return (date.fromisoformat(bit) + timedelta(days=1)).isoformat()
    except ValueError:
        return bit


def _cha_tl_sql(alias: str = "c") -> str:
    """
    Cari hareket tutarını TL'ye çevirir.

    cha_meblag orijinal döviz cinsindendir; TL hesaplarda (cha_d_cins=0) kur ile çarpılmaz.
    Her harekete cha_d_kur uygulamak banka bakiyesini onlarca kat şişirebilir.
    """
    a = alias
    return (
        f"CASE WHEN {a}.cha_meblag_ana_doviz_icin_gecersiz_fl = 1 THEN 0 "
        f"WHEN {a}.cha_d_cins = 0 THEN {a}.cha_meblag "
        f"ELSE {a}.cha_meblag * ISNULL(NULLIF({a}.cha_d_kur, 0), 1) END"
    )


def fetch_stok_ozet(client: MikroClient, bas: str, bit: str) -> list[dict[str, Any]]:
    """
    Dönem (bas..bit) için STOK_HAREKETLERI özeti: hareket türü başına tutar/miktar/adet.

    Nakit & Kârlılık'ın brüt marj ayağı buradan kurulur — resmi GL'deki 602/623 gibi
    sınıflama/kapanış kalemlerinden bağımsız, FİİLEN depodan çıkan/giren mala dayanır.
    sth_tip (0=giriş/alış, 1=çıkış/satış) + sth_evraktip ile sınıflanır (bkz. MIKRO-SEMA-NOTLARI):
      tip=1,evraktip=1 → satış irsaliyesi · tip=1,evraktip=4 → satış faturası
      tip=0,evraktip=3 → alış faturası   · tip=0,evraktip=12 → alış irsaliyesi/depo girişi
    Tarih: belge tarihi doluysa onu, değilse hareket tarihini (sth_tarih) kullanır.
    Sınıflandırma analizöre (gercek_durum) bırakılır; burada yalnız ham kırılım döner.
    """
    tarih = (
        "CASE WHEN sth_belge_tarih IS NOT NULL AND sth_belge_tarih >= '2000-01-01' "
        "THEN sth_belge_tarih ELSE sth_tarih END"
    )
    sql = (
        "SELECT sth_tip, sth_evraktip, "
        "SUM(sth_tutar) AS tutar, SUM(sth_miktar) AS miktar, COUNT(*) AS adet "
        "FROM STOK_HAREKETLERI WITH (NOLOCK) "
        f"WHERE {tarih} >= '{bas}' AND {tarih} < '{_bit_son(bit)}' "
        "GROUP BY sth_tip, sth_evraktip"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_stok_aylik(client: MikroClient, bas: str, bit: str) -> list[dict[str, Any]]:
    """Dönem içi STOK_HAREKETLERI'nin AYLIK kırılımı (trend için): ay × tip × evraktip → tutar."""
    tarih = (
        "CASE WHEN sth_belge_tarih IS NOT NULL AND sth_belge_tarih >= '2000-01-01' "
        "THEN sth_belge_tarih ELSE sth_tarih END"
    )
    sql = (
        f"SELECT CONVERT(char(7), {tarih}, 126) AS ay, sth_tip, sth_evraktip, "
        "SUM(sth_tutar) AS tutar "
        "FROM STOK_HAREKETLERI WITH (NOLOCK) "
        f"WHERE {tarih} >= '{bas}' AND {tarih} < '{_bit_son(bit)}' "
        f"GROUP BY CONVERT(char(7), {tarih}, 126), sth_tip, sth_evraktip "
        "ORDER BY ay"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_nakit_ozet(client: MikroClient, bas: str, bit: str) -> list[dict[str, Any]]:
    """
    Dönem (bas..bit) için banka nakit akışı: giren / çıkan (TL).

    Banka tarafı satırı CARI_HESAP_HAREKETLERI ⨝ BANKALAR (cha_kod = ban_kod) ile alınır
    (çift sayım önlenir). cha_tip 0=giriş (para geldi), 1=çıkış (para gitti).
    TL = cha_meblag * ISNULL(cha_d_kur, 1). cha_iptal=0 şart. Bkz. MIKRO-SEMA-NOTLARI.
    Nakit, tahakkuk zamanlamasından bağımsız fiili bir performans sinyalidir.
    """
    tl = _cha_tl_sql("c")
    sql = (
        "SELECT "
        f"SUM(CASE WHEN c.cha_tip = 0 THEN {tl} ELSE 0 END) AS giren, "
        f"SUM(CASE WHEN c.cha_tip = 1 THEN {tl} ELSE 0 END) AS cikan "
        "FROM CARI_HESAP_HAREKETLERI c WITH (NOLOCK) "
        "INNER JOIN BANKALAR b WITH (NOLOCK) ON b.ban_kod = c.cha_kod "
        f"WHERE c.cha_iptal = 0 AND ISNULL(c.cha_hidden, 0) = 0 "
        f"AND c.cha_tarihi >= '{bas}' AND c.cha_tarihi < '{_bit_son(bit)}'"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_nakit_aylik(client: MikroClient, bas: str, bit: str) -> list[dict[str, Any]]:
    """Dönem içi banka nakit akışının AYLIK kırılımı (trend için): ay → giren/çıkan (TL)."""
    tl = _cha_tl_sql("c")
    sql = (
        "SELECT CONVERT(char(7), c.cha_tarihi, 126) AS ay, "
        f"SUM(CASE WHEN c.cha_tip = 0 THEN {tl} ELSE 0 END) AS giren, "
        f"SUM(CASE WHEN c.cha_tip = 1 THEN {tl} ELSE 0 END) AS cikan "
        "FROM CARI_HESAP_HAREKETLERI c WITH (NOLOCK) "
        "INNER JOIN BANKALAR b WITH (NOLOCK) ON b.ban_kod = c.cha_kod "
        f"WHERE c.cha_iptal = 0 AND ISNULL(c.cha_hidden, 0) = 0 "
        f"AND c.cha_tarihi >= '{bas}' AND c.cha_tarihi < '{_bit_son(bit)}' "
        "GROUP BY CONVERT(char(7), c.cha_tarihi, 126) "
        "ORDER BY ay"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_bakiye_ozet(client: MikroClient, asof: str) -> list[dict[str, Any]]:
    """
    Tarih (asof) itibarıyla nakit/alacak/borç ana hesap bakiyeleri (3 hane): SUM(fis_meblag0).

    Nakit & Kârlılık'ın "param var mı / kim kime borçlu" ayağı: 10x (kasa/banka), 12x (alacaklar),
    32x (satıcı borçları). bakiye>0 = borç bakiyesi (varlık), bakiye<0 = alacak bakiyesi (borç).
    """
    sql = (
        "SELECT LEFT(fis_hesap_kod, 3) AS ana, SUM(fis_meblag0) AS bakiye "
        "FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        f"WHERE fis_iptal = 0 AND fis_tarih < '{_bit_son(asof)}' AND ("
        "fis_hesap_kod LIKE '100%' OR fis_hesap_kod LIKE '101%' OR fis_hesap_kod LIKE '102%' "
        "OR fis_hesap_kod LIKE '103%' OR fis_hesap_kod LIKE '108%' "
        "OR fis_hesap_kod LIKE '120%' OR fis_hesap_kod LIKE '121%' "
        "OR fis_hesap_kod LIKE '320%' OR fis_hesap_kod LIKE '321%') "
        "GROUP BY LEFT(fis_hesap_kod, 3)"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_mizan(client: MikroClient, asof: str) -> list[dict[str, Any]]:
    """
    Belirli tarihe (asof = 'YYYY-MM-DD') kadar kümülatif mizan: hesap başına borç/alacak.

    KRİTİK: fis_meblag0 = İŞARETLİ TL tutar (poz=borç, neg=alacak). meblag1=USD (alacak DEĞİL).
    bakiye = SUM(fis_meblag0). Mikro'nun kendi mizanıyla kuruşu kuruşuna doğrulandı.
    Bitiş günü tam dahil: fis_tarih < (asof+1gün) — datetime'da <= asof gün-içi saatleri kaçırır.
    Dönüş: [{'hesap_kodu','borc','alacak'}, ...] — mizan_bilanco.build_bilanco() bunu yer.
    """
    sql = (
        "SELECT fis_hesap_kod AS hesap_kodu, "
        "SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc, "
        "SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak "
        "FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        f"WHERE fis_iptal = 0 AND fis_tarih < '{_bit_son(asof)}' "
        "GROUP BY fis_hesap_kod"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_cari_bakiye(client: MikroClient, asof: str) -> list[dict[str, Any]]:
    """
    Tarih (asof) itibarıyla cari/banka/kasa bakiyeleri — CARI_HESAP_HAREKETLERI üzerinden.

    Banka → BANKALAR, kasa → KASALAR. ban_hesap_tip / muh_kod Python'da filtrelenir.
    Sorgu sade tutulur — bilinmeyen kolon Mikro'da sessiz boş sonuç döndürür.
    """
    rows = _fetch_cari_bakiye_sql(client, asof, genis=True)
    if rows:
        return rows
    return _fetch_cari_bakiye_sql(client, asof, genis=False)


def _fetch_cari_bakiye_sql(client: MikroClient, asof: str, *, genis: bool) -> list[dict[str, Any]]:
    tl = _cha_tl_sql("c")
    borc_h = f"SUM(CASE WHEN c.cha_tip = 0 THEN {tl} ELSE 0 END)"
    alacak_h = f"SUM(CASE WHEN c.cha_tip = 1 THEN {tl} ELSE 0 END)"
    ek = ""
    if genis:
        ek = (
            "MAX(ISNULL(ch.cari_muh_kod, '')) AS cari_muh_kod, "
            "MAX(ISNULL(b.ban_muh_kod, '')) AS ban_muh_kod, "
            "MAX(ISNULL(CAST(b.ban_hesap_tip AS int), -1)) AS ban_hesap_tip, "
            "MAX(ISNULL(b.ban_ismi, '')) AS ban_ismi, "
        )
    sql = (
        "SELECT "
        "CASE WHEN b.ban_kod IS NOT NULL THEN 2 WHEN k.kas_kod IS NOT NULL THEN 4 ELSE 0 END AS cins, "
        "ISNULL(ch.cari_hareket_tipi, 0) AS hareket_tipi, "
        "ISNULL(ch.cari_baglanti_tipi, 2) AS baglanti_tipi, "
        f"{ek}"
        "c.cha_kod AS kod, "
        f"{borc_h} AS borc_h, {alacak_h} AS alacak_h "
        "FROM CARI_HESAP_HAREKETLERI c WITH (NOLOCK) "
        "LEFT JOIN BANKALAR b WITH (NOLOCK) ON b.ban_kod = c.cha_kod "
        "LEFT JOIN KASALAR k WITH (NOLOCK) ON k.kas_kod = c.cha_kod "
        "LEFT JOIN CARI_HESAPLAR ch WITH (NOLOCK) ON ch.cari_kod = c.cha_kod AND ch.cari_iptal = 0 "
        f"WHERE c.cha_iptal = 0 AND ISNULL(c.cha_hidden, 0) = 0 "
        f"AND c.cha_tarihi < '{_bit_son(asof)}' "
        "AND (b.ban_kod IS NOT NULL OR k.kas_kod IS NOT NULL OR c.cha_cari_cins = 0) "
        "GROUP BY "
        "CASE WHEN b.ban_kod IS NOT NULL THEN 2 WHEN k.kas_kod IS NOT NULL THEN 4 ELSE 0 END, "
        "ISNULL(ch.cari_hareket_tipi, 0), ISNULL(ch.cari_baglanti_tipi, 2), c.cha_kod "
        f"HAVING ABS({borc_h} - {alacak_h}) >= 0.005"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))


def fetch_cari_vade_gun(client: MikroClient) -> dict[str, int]:
    """
    Cari kod → vade günü haritası (ödeme planından). cha_vade bu kurulumda boş olduğu için
    vade = evrak tarihi + bu gün sayısıyla hesaplanır (ss/lib/mikro-api vade-takip ile aynı).

    cari_odemeplan_no → ODEME_PLANLARI.odp_ortgun / odp_adi. Hata olursa boş harita döner
    (vade = evrak tarihi'ne düşer; yaşlandırma yine çalışır, yalnız "gecikmiş" tarafa kayar).
    """
    sql = (
        "SELECT cari_kod, CAST(cari_odemeplan_no AS int) AS plan_no, "
        "(SELECT odp_ortgun FROM ODEME_PLANLARI WHERE odp_no = cari_odemeplan_no) AS ortgun, "
        "(SELECT odp_adi FROM ODEME_PLANLARI WHERE odp_no = cari_odemeplan_no) AS plan_adi "
        "FROM CARI_HESAPLAR WITH (NOLOCK) "
        "WHERE cari_kod LIKE '120%' OR cari_kod LIKE '320%'"
    )
    out: dict[str, int] = {}
    try:
        rows = parse_sql_rows(client.sql_veri_oku(sql, timeout=60, max_attempts=2))
    except MikroAPIError:
        return out
    for r in rows:
        kod = str(get_row_value(r, "cari_kod", "CARI_KOD") or "").strip()
        if not kod:
            continue
        plan_no = _opt_int(get_row_value(r, "plan_no", "PLAN_NO"))
        ortgun = _opt_int(get_row_value(r, "ortgun", "ORTGUN"))
        plan_adi = get_row_value(r, "plan_adi", "PLAN_ADI")
        vg = hesapla_vade_gun(plan_no, str(plan_adi) if plan_adi is not None else None, ortgun)
        if vg is not None:
            out[kod] = vg
    return out


def _opt_int(v: object) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def fetch_acik_kalemler(
    client: MikroClient, asof: str, bas: str, bit: str,
) -> list[dict[str, Any]]:
    """
    Tahsilat & Alacak için cari açık kalemleri — CARI_HESAP_HAREKETLERI, 120/320 cariler.

    Her cari için (cha_tip, evrak tarihi, cha_vade) kırılımında kümülatif tutar (asof) + dönem
    içi tutar (bas..bit) döner. Vade Python'da hesaplanır: cha_vade doluysa o, yoksa evrak tarihi
    + carinin ödeme planı günü (fetch_cari_vade_gun). 120.B* (özel) hariç. Banka/kasa zaten
    120/320 önekiyle doğal olarak elenir.
    """
    tl = _cha_tl_sql("c")
    donem = (
        f"SUM(CASE WHEN c.cha_tarihi >= '{bas}' AND c.cha_tarihi < '{_bit_son(bit)}' "
        f"THEN {tl} ELSE 0 END)"
    )
    sql = (
        "SELECT c.cha_kod AS kod, "
        "MAX(ISNULL(ch.cari_unvan1, '')) AS unvan, "
        "c.cha_tip AS tip, "
        "CONVERT(date, c.cha_tarihi) AS evrak_tarihi, "
        "CONVERT(date, c.cha_vade) AS cha_vade, "
        f"SUM({tl}) AS tutar, "
        f"{donem} AS tutar_donem "
        "FROM CARI_HESAP_HAREKETLERI c WITH (NOLOCK) "
        "LEFT JOIN CARI_HESAPLAR ch WITH (NOLOCK) ON ch.cari_kod = c.cha_kod AND ch.cari_iptal = 0 "
        "WHERE c.cha_iptal = 0 AND ISNULL(c.cha_hidden, 0) = 0 "
        f"AND c.cha_tarihi < '{_bit_son(asof)}' "
        "AND (c.cha_kod LIKE '120%' OR c.cha_kod LIKE '320%') "
        "AND c.cha_kod NOT LIKE '120.B%' AND ISNULL(c.cha_meblag, 0) <> 0 "
        "GROUP BY c.cha_kod, c.cha_tip, CONVERT(date, c.cha_tarihi), CONVERT(date, c.cha_vade) "
        f"HAVING ABS(SUM({tl})) >= 0.005"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=180, max_attempts=2))
