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

from typing import Any

import pandas as pd

from bank_parser import STANDARD_BANK_COLUMNS
from fatura_parser import STANDARD_FATURA_COLUMNS
from mikro_api import MikroClient, get_row_value, parse_sql_rows
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
    # Muavin (genel muhasebe hareketleri). GL detay tablosu sürüme göre değişebilir.
    "muavin": """
        SELECT
            mh.mha_tarihi      AS tarih,
            mh.mha_hesapno     AS hesap_kodu,
            hp.muh_isim        AS hesap_adi,
            CASE WHEN mh.mha_RB = 0 THEN mh.mha_meblag ELSE 0 END AS borc,
            CASE WHEN mh.mha_RB = 1 THEN mh.mha_meblag ELSE 0 END AS alacak,
            mh.mha_aciklama    AS aciklama,
            mh.mha_evrakno_sira AS evrak_no
        FROM MUHASEBE_HAREKETLERI mh
        LEFT JOIN MUHASEBE_HESAP_PLANLARI hp ON hp.muh_hesap_kodu = mh.mha_hesapno
        WHERE mh.mha_tarihi >= '{ilk}' AND mh.mha_tarihi <= '{son}'
    """,
    # Alış faturaları — STOK_HAREKETLERI satır bazlı (sth_tip=0 giriş/alış).
    "alis_fatura": """
        SELECT
            (sth_evrakno_seri + '-' + CAST(sth_evrakno_sira AS varchar(20))) AS fatura_no,
            sth_belge_no   AS belge_no,
            sth_tarih      AS tarih,
            sth_vade_tarihi AS vade,
            sth_cari_kodu  AS cari_kodu,
            sth_stok_kod   AS stok_kodu,
            sth_miktar     AS miktar,
            sth_tutar      AS net_tutar
        FROM STOK_HAREKETLERI
        WHERE sth_tip = 0 AND sth_evraktip IN (3, 4)
          AND sth_tarih >= '{ilk}' AND sth_tarih <= '{son}'
    """,
    # Satış faturaları — STOK_HAREKETLERI satır bazlı (sth_tip=1 çıkış/satış).
    "satis_fatura": """
        SELECT
            (sth_evrakno_seri + '-' + CAST(sth_evrakno_sira AS varchar(20))) AS fatura_no,
            sth_belge_no   AS belge_no,
            sth_tarih      AS tarih,
            sth_vade_tarihi AS vade,
            sth_cari_kodu  AS cari_kodu,
            sth_stok_kod   AS stok_kodu,
            sth_miktar     AS miktar,
            sth_tutar      AS net_tutar
        FROM STOK_HAREKETLERI
        WHERE sth_tip = 1 AND sth_evraktip IN (3, 4)
          AND sth_tarih >= '{ilk}' AND sth_tarih <= '{son}'
    """,
    # Banka hareketleri — 102 (banka) hesaplarının GL hareketleri + karşı hesap.
    "banka": """
        SELECT
            mh.mha_tarihi   AS tarih,
            mh.mha_aciklama AS evrak_tipi,
            CASE WHEN mh.mha_RB = 0 THEN mh.mha_meblag ELSE 0 END AS borc,
            CASE WHEN mh.mha_RB = 1 THEN mh.mha_meblag ELSE 0 END AS alacak,
            mh.mha_karsi_hesapno AS cari_kodu,
            kp.muh_isim     AS karsi_hesap_ismi
        FROM MUHASEBE_HAREKETLERI mh
        LEFT JOIN MUHASEBE_HESAP_PLANLARI kp ON kp.muh_hesap_kodu = mh.mha_karsi_hesapno
        WHERE mh.mha_hesapno LIKE '102%'
          AND mh.mha_tarihi >= '{ilk}' AND mh.mha_tarihi <= '{son}'
    """,
}


def _sql_for(kaynak: str, analiz_ayi: str) -> str:
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    return SORGULAR[kaynak].format(ilk=bas.isoformat(), son=bit.isoformat())


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
        aciklama = " — ".join(p for p in (evrak, isim) if p)
        prefix = karsi_prefix(cari)
        records.append({
            "tarih": get_row_value(r, "tarih", "mha_tarihi"),
            "evrak_tipi": evrak,
            "aciklama": aciklama,
            "giris": giris,
            "cikis": cikis,
            "bakiye": _net_bakiye(get_row_value(r, "borc_bakiye"), get_row_value(r, "alacak_bakiye")),
            "cari_kodu": cari,
            "karsi_hesap_prefix": prefix,
            "banka_adi": banka_adi,
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
