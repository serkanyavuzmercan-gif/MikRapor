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


def fetch_mizan(client: MikroClient, asof: str) -> list[dict[str, Any]]:
    """
    Belirli tarihe (asof = 'YYYY-MM-DD') kadar kümülatif mizan: hesap başına borç/alacak.

    KRİTİK: fis_meblag0 = İŞARETLİ TL tutar (poz=borç, neg=alacak). meblag1=USD (alacak DEĞİL).
    bakiye = SUM(fis_meblag0). Mikro'nun kendi mizanıyla kuruşu kuruşuna doğrulandı.
    Dönüş: [{'hesap_kodu','borc','alacak'}, ...] — mizan_bilanco.build_bilanco() bunu yer.
    """
    sql = (
        "SELECT fis_hesap_kod AS hesap_kodu, "
        "SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc, "
        "SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak "
        "FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        f"WHERE fis_iptal = 0 AND fis_tarih <= '{asof}' "
        "GROUP BY fis_hesap_kod"
    )
    return parse_sql_rows(client.sql_veri_oku(sql, timeout=120, max_attempts=2))
