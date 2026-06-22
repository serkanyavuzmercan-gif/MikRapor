"""
Banka hareketlerinden nakit akış özeti.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from parse_utils import format_tl
from period_utils import analiz_ayi_araligi, filter_df_by_analiz_ayi


@dataclass
class BankaOzetSatir:
    banka_adi: str
    donem_basi: float
    girisler: float
    cikislar: float
    donem_sonu: float
    ic_transfer_giris: float = 0.0
    ic_transfer_cikis: float = 0.0


@dataclass
class NakitAkisOzeti:
    analiz_ayi: str = ""
    donem_basi_mevcut: float = 0.0
    donem_ici_girisler: float = 0.0
    donem_ici_cikislar: float = 0.0
    donem_sonu_net_nakit: float = 0.0
    ic_transfer_giris: float = 0.0
    ic_transfer_cikis: float = 0.0
    giris_transfer_haric: float = 0.0
    cikis_transfer_haric: float = 0.0
    banka_kirilim: list[BankaOzetSatir] = field(default_factory=list)
    tahmini_donem_basi: bool = False
    yorum: str = ""


def _is_ic_transfer(row: pd.Series) -> bool:
    if "ic_transfer" in row.index:
        val = row.get("ic_transfer")
        if pd.notna(val):
            return bool(val)
    prefix = str(row.get("karsi_hesap_prefix", ""))
    return prefix == "102"


def _bank_period_summary(banka_df: pd.DataFrame, analiz_ayi: str) -> BankaOzetSatir:
    bas, bit = analiz_ayi_araligi(analiz_ayi)
    banka_adi = str(banka_df["banka_adi"].iloc[0]) if not banka_df.empty else ""
    work = banka_df.sort_values("tarih").copy()

    ay_mask = (work["tarih"].dt.date >= bas) & (work["tarih"].dt.date <= bit)
    ay_rows = work[ay_mask]
    onceki = work[work["tarih"].dt.date < bas]

    girisler = float(ay_rows["giris"].sum()) if not ay_rows.empty else 0.0
    cikislar = float(ay_rows["cikis"].sum()) if not ay_rows.empty else 0.0

    ic_giris = 0.0
    ic_cikis = 0.0
    if not ay_rows.empty:
        ic_mask = ay_rows.apply(_is_ic_transfer, axis=1)
        ic_giris = float(ay_rows.loc[ic_mask, "giris"].sum())
        ic_cikis = float(ay_rows.loc[ic_mask, "cikis"].sum())

    donem_sonu = 0.0
    donem_basi = 0.0
    if not ay_rows.empty and "bakiye" in ay_rows.columns:
        donem_sonu = float(ay_rows.iloc[-1]["bakiye"])
    elif not work.empty and "bakiye" in work.columns:
        donem_sonu = float(work.iloc[-1]["bakiye"])

    if not onceki.empty and "bakiye" in onceki.columns:
        donem_basi = float(onceki.iloc[-1]["bakiye"])
    elif not ay_rows.empty:
        first = ay_rows.iloc[0]
        hareket = float(first["giris"]) - float(first["cikis"])
        donem_basi = float(first["bakiye"]) - hareket

    return BankaOzetSatir(
        banka_adi=banka_adi,
        donem_basi=donem_basi,
        girisler=girisler,
        cikislar=cikislar,
        donem_sonu=donem_sonu,
        ic_transfer_giris=ic_giris,
        ic_transfer_cikis=ic_cikis,
    )


def analyze_nakit_akis(banka_df: pd.DataFrame, analiz_ayi: str) -> NakitAkisOzeti:
    """Seçilen ay için konsolide nakit akış özetini üretir."""
    if banka_df is None or banka_df.empty:
        return NakitAkisOzeti(
            analiz_ayi=analiz_ayi,
            yorum="Banka hareketi yüklenmedi.",
        )

    work = banka_df.copy()
    work["tarih"] = pd.to_datetime(work["tarih"], errors="coerce", dayfirst=True)

    kirilim: list[BankaOzetSatir] = []
    for banka_adi, grp in work.groupby("banka_adi", sort=False):
        kirilim.append(_bank_period_summary(grp, analiz_ayi))

    donem_basi = sum(k.donem_basi for k in kirilim)
    girisler = sum(k.girisler for k in kirilim)
    cikislar = sum(k.cikislar for k in kirilim)
    donem_sonu = sum(k.donem_sonu for k in kirilim)
    ic_giris = sum(k.ic_transfer_giris for k in kirilim)
    ic_cikis = sum(k.ic_transfer_cikis for k in kirilim)

    tahmini = any(
        filter_df_by_analiz_ayi(
            work[work["banka_adi"] == k.banka_adi], "tarih", analiz_ayi
        ).empty
        and k.donem_basi != 0
        for k in kirilim
    )

    yorum = (
        f"Dönem başı {format_tl(donem_basi)}, giriş {format_tl(girisler)}, "
        f"çıkış {format_tl(cikislar)}, dönem sonu {format_tl(donem_sonu)}."
    )
    if ic_giris > 0 or ic_cikis > 0:
        yorum += (
            f" Hesaplar arası transfer (102): giriş {format_tl(ic_giris)}, "
            f"çıkış {format_tl(ic_cikis)} — operasyonel akış için transfer hariç "
            f"giriş {format_tl(girisler - ic_giris)}, çıkış {format_tl(cikislar - ic_cikis)}."
        )
    if tahmini:
        yorum += " Dönem başı bakiye kısmen tahmini hesaplandı."

    return NakitAkisOzeti(
        analiz_ayi=analiz_ayi,
        donem_basi_mevcut=donem_basi,
        donem_ici_girisler=girisler,
        donem_ici_cikislar=cikislar,
        donem_sonu_net_nakit=donem_sonu,
        ic_transfer_giris=ic_giris,
        ic_transfer_cikis=ic_cikis,
        giris_transfer_haric=girisler - ic_giris,
        cikis_transfer_haric=cikislar - ic_cikis,
        banka_kirilim=kirilim,
        tahmini_donem_basi=tahmini,
        yorum=yorum,
    )
