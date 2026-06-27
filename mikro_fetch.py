"""
Mikro API → analiz DataFrame'leri köprüsü (KONTRAT ADAPTÖRÜ).

Bu modül, elle Excel/CSV yükleme yerine Mikro REST API'den veri çeker ve **mevcut
parser'ların ürettiği DataFrame şeklinin (STANDARD_*_COLUMNS) BİREBİR aynısını** üretir.
Böylece analizör katmanı (analyzer.py ve altındakiler) HİÇ değişmeden çalışır.

Tasarım — iki katman bilinçli olarak ayrıldı:
  1. SAF EŞLEME (`rows_to_*_df`): Mikro satır-sözlüklerini standart DataFrame'e çevirir.
     Network gerektirmez, birim testlerle doğrulanır → kontratın garantisi burada.
  2. SQL (`SORGULAR`): Mikro MSSQL'den veriyi çeken ham sorgular.

╔══════════════════════════════════════════════════════════════════════════════╗
║ ⚠️  DOĞRULANACAK — SQL tablo/kolon adları Mikro sürümüne göre DEĞİŞEBİLİR.      ║
║ Aşağıdaki sorgular ss/lib/mikro-api.ts'te doğrulanmış desene (STOK_HAREKETLERI ║
║ sth_*, CARI_HESAPLAR cari_*) dayanır; muavin/banka GL sorguları en az emin     ║
║ olanlardır. İLK CANLI MİKRO BAĞLANTISINDA bu sorguları teyit edip gerekiyorsa  ║
║ buradan (tek yer) düzeltin. Eşleme katmanı satır anahtarlarını esnek okur      ║
║ (get_row_value: aynen/UPPER/lower) → kolon büyük/küçük harfi sorun olmaz.       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from bank_parser import STANDARD_BANK_COLUMNS
from fatura_parser import STANDARD_FATURA_COLUMNS
from mikro_api import MikroAPIError, MikroClient, get_row_value, parse_sql_rows
from muavin_parser import STANDARD_MUAVIN_COLUMNS
from parse_utils import (
    extract_ana_hesap,
    is_alt_hesap,
    karsi_prefix,
    normalize_hesap_kodu,
    parse_turkish_amount,
)
from period_utils import analiz_ayi_araligi

KAYNAK_ETIKET = "Mikro API"


# ---------------------------------------------------------------------------
# SQL sorguları (DOĞRULANACAK — bkz. modül başı uyarısı). {ilk}/{son} = 'YYYY-MM-DD'.
# ---------------------------------------------------------------------------

SORGULAR: dict[str, str] = {
    # Muavin (genel muhasebe / GL satırları) — MUHASEBE_FISLERI (fis_*), canlı doğrulandı.
    # fis_meblag0 = borç, fis_meblag1 = alacak (Mikro standart muavin yapısı).
    "muavin": """
        SELECT
            fis_tarih      AS tarih,
            fis_hesap_kod  AS hesap_kodu,
            fis_meblag0    AS borc,
            fis_meblag1    AS alacak,
            fis_aciklama1  AS aciklama,
            fis_sira_no    AS evrak_no
        FROM MUHASEBE_FISLERI WITH (NOLOCK)
        WHERE fis_iptal = 0
          AND fis_tarih >= '{ilk}' AND fis_tarih < '{son1}'
    """,
    # Alış faturası — STOK_HAREKETLERI sth_tip=0, sth_evraktip=3 (canlı doğrulandı).
    "alis_fatura": """
        SELECT
            (sth_evrakno_seri + '-' + CAST(sth_evrakno_sira AS varchar(20))) AS fatura_no,
            sth_belge_no   AS belge_no,
            sth_tarih      AS tarih,
            sth_cari_kodu  AS cari_kodu,
            sth_stok_kod   AS stok_kodu,
            sth_miktar     AS miktar,
            sth_tutar      AS net_tutar
        FROM STOK_HAREKETLERI WITH (NOLOCK)
        WHERE sth_tip = 0 AND sth_evraktip = 3
          AND sth_tarih >= '{ilk}' AND sth_tarih < '{son1}'
    """,
    # Satış faturası — STOK_HAREKETLERI sth_tip=1, sth_evraktip=4 (canlı doğrulandı).
    "satis_fatura": """
        SELECT
            (sth_evrakno_seri + '-' + CAST(sth_evrakno_sira AS varchar(20))) AS fatura_no,
            sth_belge_no   AS belge_no,
            sth_tarih      AS tarih,
            sth_cari_kodu  AS cari_kodu,
            sth_stok_kod   AS stok_kodu,
            sth_miktar     AS miktar,
            sth_tutar      AS net_tutar
        FROM STOK_HAREKETLERI WITH (NOLOCK)
        WHERE sth_tip = 1 AND sth_evraktip = 4
          AND sth_tarih >= '{ilk}' AND sth_tarih < '{son1}'
    """,
    # Banka — CARI_HESAP_HAREKETLERI'nin BANKA tarafı (cha_kod = ban_kod). cha_tip 0=giriş,1=çıkış.
    # Karşı taraf (cari): aynı evrak no'lu, banka OLMAYAN diğer satırın cha_kod'u (ss/banka-bildirim.ts).
    "banka": """
        SELECT
            CHA.cha_tarihi   AS tarih,
            B.ban_ismi       AS banka_adi,
            CHA.cha_aciklama AS aciklama,
            CASE WHEN CHA.cha_tip = 0 THEN CHA.cha_meblag * ISNULL(CHA.cha_d_kur, 1) ELSE 0 END AS giris,
            CASE WHEN CHA.cha_tip = 1 THEN CHA.cha_meblag * ISNULL(CHA.cha_d_kur, 1) ELSE 0 END AS cikis,
            KARSI.cari_kod   AS cari_kodu
        FROM CARI_HESAP_HAREKETLERI AS CHA WITH (NOLOCK)
        INNER JOIN BANKALAR AS B WITH (NOLOCK) ON B.ban_kod = CHA.cha_kod
        OUTER APPLY (
            SELECT TOP 1 K.cha_kod AS cari_kod
            FROM CARI_HESAP_HAREKETLERI AS K WITH (NOLOCK)
            WHERE K.cha_evrakno_seri = CHA.cha_evrakno_seri
              AND K.cha_evrakno_sira = CHA.cha_evrakno_sira
              AND K.cha_Guid <> CHA.cha_Guid AND K.cha_iptal = 0
              AND NOT EXISTS (SELECT 1 FROM BANKALAR BB WHERE BB.ban_kod = K.cha_kod)
        ) AS KARSI
        WHERE CHA.cha_iptal = 0
          AND CHA.cha_tarihi >= '{ilk}' AND CHA.cha_tarihi < '{son1}'
    """,
}


def _sql_for(kaynak: str, analiz_ayi: str) -> str:
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    son1 = bit + timedelta(days=1)  # ay sonunu dahil etmek için: < ertesi-gün (datetime saatleri kaçmasın)
    return SORGULAR[kaynak].format(ilk=bas.isoformat(), son1=son1.isoformat())


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


# ---------------------------------------------------------------------------
# SAF EŞLEME — Mikro satırları → standart DataFrame (network'süz, test edilir)
# ---------------------------------------------------------------------------

def rows_to_muavin_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Mikro GL satırlarını muavin_parser STANDARD_MUAVIN_COLUMNS şekline çevirir."""
    records: list[dict[str, Any]] = []
    for r in rows:
        hesap = normalize_hesap_kodu(get_row_value(r, "hesap_kodu", "hesapno", "mha_hesapno"))
        borc = parse_turkish_amount(get_row_value(r, "borc", "tl_borc", "mha_borc"))
        alacak = parse_turkish_amount(get_row_value(r, "alacak", "tl_alacak", "mha_alacak"))
        if not hesap or (borc == 0 and alacak == 0):
            continue
        records.append({
            "tarih": get_row_value(r, "tarih", "mha_tarihi"),
            "hesap_kodu": hesap,
            "hesap_adi": _to_str(get_row_value(r, "hesap_adi", "muh_isim")),
            "tl_borc": borc,
            "tl_alacak": alacak,
            "aciklama": _to_str(get_row_value(r, "aciklama", "mha_aciklama")),
            "cari_kodu": _to_str(get_row_value(r, "cari_kodu")),
            "evrak_no": _to_str(get_row_value(r, "evrak_no", "evrakno", "mha_evrakno_sira")),
        })
    if not records:
        return _empty(STANDARD_MUAVIN_COLUMNS)

    df = pd.DataFrame(records)
    df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce", dayfirst=True)
    df["ana_hesap"] = df["hesap_kodu"].apply(extract_ana_hesap)
    df["alt_hesap"] = df["hesap_kodu"].apply(is_alt_hesap)
    df = df[df["tarih"].notna()].copy()
    if df.empty:
        return _empty(STANDARD_MUAVIN_COLUMNS)
    return df[STANDARD_MUAVIN_COLUMNS].copy()


def rows_to_fatura_df(rows: list[dict[str, Any]], fatura_turu: str) -> pd.DataFrame:
    """Mikro STOK_HAREKETLERI satırlarını fatura_parser STANDARD_FATURA_COLUMNS şekline çevirir."""
    records: list[dict[str, Any]] = []
    for r in rows:
        stok = _to_str(get_row_value(r, "stok_kodu", "sth_stok_kod"))
        miktar = pd.to_numeric(get_row_value(r, "miktar", "sth_miktar"), errors="coerce")
        miktar = float(miktar) if pd.notna(miktar) else 0.0
        net_tutar = parse_turkish_amount(get_row_value(r, "net_tutar", "sth_tutar"))
        if not stok or miktar <= 0 or net_tutar == 0:
            continue
        records.append({
            "fatura_no": _to_str(get_row_value(r, "fatura_no")),
            "belge_no": _to_str(get_row_value(r, "belge_no", "sth_belge_no")),
            "cins": _to_str(get_row_value(r, "cins")),
            "tarih": get_row_value(r, "tarih", "sth_tarih"),
            "vade": get_row_value(r, "vade", "sth_vade_tarihi"),
            "cari_kodu": _to_str(get_row_value(r, "cari_kodu", "sth_cari_kodu")),
            "cari_adi": _to_str(get_row_value(r, "cari_adi")),
            "stok_kodu": stok,
            "stok_adi": _to_str(get_row_value(r, "stok_adi")),
            "miktar": miktar,
            "net_bf": parse_turkish_amount(get_row_value(r, "net_bf")),
            "net_tutar": net_tutar,
            "stok_dvz": _to_str(get_row_value(r, "stok_dvz")) or "TL",
            "fatura_turu": fatura_turu,
            "dokum_tarihi": "",
            "kaynak_dosya": KAYNAK_ETIKET,
            "kaynak_ay": "",
        })
    if not records:
        return _empty(STANDARD_FATURA_COLUMNS)

    df = pd.DataFrame(records)
    df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce", dayfirst=True)
    df["vade"] = pd.to_datetime(df["vade"], errors="coerce", dayfirst=True)
    return df[STANDARD_FATURA_COLUMNS].copy()


def rows_to_banka_df(rows: list[dict[str, Any]], banka_adi: str = KAYNAK_ETIKET) -> pd.DataFrame:
    """Mikro 102 GL satırlarını bank_parser STANDARD_BANK_COLUMNS şekline çevirir."""
    records: list[dict[str, Any]] = []
    for r in rows:
        giris = parse_turkish_amount(get_row_value(r, "giris", "borc", "tl_borc"))
        cikis = parse_turkish_amount(get_row_value(r, "cikis", "alacak", "tl_alacak"))
        cari = _to_str(get_row_value(r, "cari_kodu"))
        evrak = _to_str(get_row_value(r, "evrak_tipi"))
        isim = _to_str(get_row_value(r, "karsi_hesap_ismi"))
        aciklama = _to_str(get_row_value(r, "aciklama")) or " — ".join(p for p in (evrak, isim) if p)
        prefix = karsi_prefix(cari)
        records.append({
            "tarih": get_row_value(r, "tarih", "mha_tarihi", "cha_tarihi"),
            "evrak_tipi": evrak,
            "aciklama": aciklama,
            "giris": giris,
            "cikis": cikis,
            "bakiye": _net_bakiye(get_row_value(r, "borc_bakiye"), get_row_value(r, "alacak_bakiye")),
            "cari_kodu": cari,
            "karsi_hesap_prefix": prefix,
            "banka_adi": _to_str(get_row_value(r, "banka_adi")) or banka_adi,
            "ic_transfer": prefix == "102",
        })
    if not records:
        return _empty(STANDARD_BANK_COLUMNS)

    df = pd.DataFrame(records)
    df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce", dayfirst=True)
    df = df[df["tarih"].notna()].copy()
    df = df[(df["giris"] != 0) | (df["cikis"] != 0) | (df["bakiye"] != 0)].copy()
    if df.empty:
        return _empty(STANDARD_BANK_COLUMNS)
    return df[STANDARD_BANK_COLUMNS].sort_values("tarih").reset_index(drop=True)


def _net_bakiye(borc_bakiye: Any, alacak_bakiye: Any) -> float:
    bb = parse_turkish_amount(borc_bakiye)
    ab = parse_turkish_amount(alacak_bakiye)
    if bb != 0:
        return bb
    if ab != 0:
        return -ab
    return 0.0


# ---------------------------------------------------------------------------
# ÇEKME — Mikro'dan oku + eşle (network gerektirir)
# ---------------------------------------------------------------------------

def fetch_muavin(client: MikroClient, analiz_ayi: str) -> pd.DataFrame:
    rows = parse_sql_rows(client.sql_veri_oku(_sql_for("muavin", analiz_ayi)))
    return rows_to_muavin_df(rows)


def fetch_alis_faturalari(client: MikroClient, analiz_ayi: str) -> pd.DataFrame:
    rows = parse_sql_rows(client.sql_veri_oku(_sql_for("alis_fatura", analiz_ayi)))
    return rows_to_fatura_df(rows, "alis")


def fetch_satis_faturalari(client: MikroClient, analiz_ayi: str) -> pd.DataFrame:
    rows = parse_sql_rows(client.sql_veri_oku(_sql_for("satis_fatura", analiz_ayi)))
    return rows_to_fatura_df(rows, "satis")


def fetch_banka(client: MikroClient, analiz_ayi: str) -> pd.DataFrame:
    rows = parse_sql_rows(client.sql_veri_oku(_sql_for("banka", analiz_ayi)))
    return rows_to_banka_df(rows)


def fetch_all(client: MikroClient, analiz_ayi: str) -> dict[str, pd.DataFrame]:
    """Seçilen ay için 4 çekirdek kaynağı çeker. Plan (120/320) v1'de elle yüklemede kalır."""
    return {
        "muavin": fetch_muavin(client, analiz_ayi),
        "alis_fatura": fetch_alis_faturalari(client, analiz_ayi),
        "satis_fatura": fetch_satis_faturalari(client, analiz_ayi),
        "banka": fetch_banka(client, analiz_ayi),
    }


# ---------------------------------------------------------------------------
# MİZAN — bilanço/gelir tablosu için (tarih itibarıyla kümülatif GL)
# ---------------------------------------------------------------------------

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
    tam dahil edilsin diye < (bit+1gün). build_gelir_tablosu() bu satırları işler; en alt satır
    (Dönem Net Kârı) bilançonun donem_kz'siyle aynı 6xx kümesinden gelir → mutabakat sağlar.
    """
    try:
        bit_son = (date.fromisoformat(bit) + timedelta(days=1)).isoformat()
    except ValueError:
        bit_son = bit
    sql = (
        "SELECT fis_hesap_kod AS hesap_kodu, "
        "SUM(CASE WHEN fis_meblag0 > 0 THEN fis_meblag0 ELSE 0 END) AS borc, "
        "SUM(CASE WHEN fis_meblag0 < 0 THEN -fis_meblag0 ELSE 0 END) AS alacak "
        "FROM MUHASEBE_FISLERI WITH (NOLOCK) "
        "WHERE fis_iptal = 0 AND fis_hesap_kod LIKE '6%' "
        f"AND fis_tarih >= '{bas}' AND fis_tarih < '{bit_son}' "
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
