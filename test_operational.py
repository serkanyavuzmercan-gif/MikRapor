"""
Ay bazlı finansal analiz entegrasyon testleri.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analyzer import run_monthly_analysis
from bank_parser import load_banka_dosyasi
from cashflow_analyzer import analyze_nakit_akis
from cfo_analyzer import analyze_cfo_uyarilari
from exporter import export_excel, export_pdf, export_text, export_word
from fatura_analyzer import analyze_fatura_kar, is_analiz_disı_stok_kodu
from fatura_parser import (
    infer_ay_from_filename,
    load_alis_faturalari_dosyalari,
    load_satis_faturalari_dosyalari,
)
from cari_plan_analyzer import CariPlanSonuc, analyze_cari_plan, compute_vade_net
from cari_plan_parser import load_tahsilat_plan, load_tediye_plan
from plan_mutabakat import build_plan_mutabakat
from reconciliation_analyzer import YaslandirmaSonuc
from trend_analyzer import compute_ay_karsilastirma
from models import AnalizVeriSeti, AylikMaasGirisi
from monthly_pl_analyzer import aggregate_muavin_gider_kalemleri, analyze_monthly_pl
from muavin_parser import load_muavin
from operational_analyzer import (
    PersonelMaas,
    is_kargo_cari_adi,
    is_kargo_fatura_satir,
)
from period_utils import analiz_ayi_araligi, filter_df_by_analiz_ayi
from reconciliation_analyzer import analyze_reconciliation, analyze_veri_eslesme, banka_120_giris_toplam

SAMPLES = Path(__file__).parent / "samples"
ANALIZ_AYI = "2026-03"
HAM_VERILER = Path(r"c:\Users\Win11\OneDrive\Masaüstü\Ham Veriler")
DESKTOP_PLAN_120 = Path(r"c:\Users\Win11\OneDrive\Masaüstü\120.xlsx")
DESKTOP_PLAN_320 = Path(r"c:\Users\Win11\OneDrive\Masaüstü\320.xlsx")


def _make_fatura_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ("tarih", "vade"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True)
    for col in ("fatura_no", "cari_kodu", "cari_adi", "stok_kodu", "stok_adi", "fatura_turu"):
        if col not in df.columns:
            df[col] = ""
    if "miktar" not in df.columns:
        df["miktar"] = 1.0
    if "net_tutar" not in df.columns:
        df["net_tutar"] = 100.0
    return df


def _make_banka_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["tarih"] = pd.to_datetime(df["tarih"], dayfirst=True)
    for col in ("giris", "cikis", "bakiye"):
        if col not in df.columns:
            df[col] = 0.0
    for col in ("cari_kodu", "aciklama", "banka_adi", "evrak_tipi", "karsi_hesap_prefix"):
        if col not in df.columns:
            df[col] = ""
    if "ic_transfer" not in df.columns:
        df["ic_transfer"] = (
            df["karsi_hesap_prefix"].astype(str).eq("102")
            | df["cari_kodu"].astype(str).str.startswith("102")
        )
    else:
        df["ic_transfer"] = df["ic_transfer"].fillna(False).astype(bool)
    return df


def _make_muavin_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["tarih"] = pd.to_datetime(df["tarih"], dayfirst=True)
    for col in ("hesap_kodu", "hesap_adi"):
        if col not in df.columns:
            df[col] = ""
    for col in ("tl_borc", "tl_alacak"):
        if col not in df.columns:
            df[col] = 0.0
    return df


class TestAyBazliMimari(unittest.TestCase):
    def test_ad_muh_exclusion(self) -> None:
        self.assertTrue(is_analiz_disı_stok_kodu("MUH001"))
        self.assertTrue(is_analiz_disı_stok_kodu("AD-MUH02"))
        self.assertFalse(is_analiz_disı_stok_kodu("STK001"))

    def test_kargo_detection(self) -> None:
        self.assertTrue(is_kargo_fatura_satir("NAKLIYE", "Nakliye bedeli"))
        self.assertTrue(is_kargo_cari_adi("ARAS KARGO"))
        self.assertFalse(is_kargo_cari_adi("KAYNAKLIK LTD"))

    def test_muavin_parser_sample(self) -> None:
        df = load_muavin(SAMPLES / "ornek_muavin_2026_03.csv")
        self.assertGreater(len(df), 0)
        kalemler = aggregate_muavin_gider_kalemleri(
            filter_df_by_analiz_ayi(df, "tarih", ANALIZ_AYI)
        )
        self.assertGreater(sum(k.tutar for k in kalemler), 100000)

    def test_banka_nakit_ozet(self) -> None:
        banka = load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv", "Test Bank")
        nakit = analyze_nakit_akis(banka, ANALIZ_AYI)
        self.assertGreater(nakit.donem_ici_girisler, 0)
        self.assertGreater(nakit.donem_ici_cikislar, 0)
        self.assertGreater(nakit.ic_transfer_cikis, 0)
        self.assertLess(nakit.cikis_transfer_haric, nakit.donem_ici_cikislar)

    def test_mikro_banka_coerce(self) -> None:
        banka = load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv")
        self.assertIn("cari_kodu", banka.columns)
        self.assertIn("karsi_hesap_prefix", banka.columns)
        tahsil = banka[(banka["giris"] > 0) & (banka["cari_kodu"].str.startswith("120"))]
        self.assertGreater(len(tahsil), 0)
        self.assertTrue((banka["cikis"] >= 0).all())
        transfer = banka[banka["ic_transfer"]]
        self.assertGreater(len(transfer), 0)

    def test_102_transfer_haric_eslesme(self) -> None:
        banka = _make_banka_df([
            {"tarih": "10.03.2026", "cikis": 50000, "cari_kodu": "102.01.001",
             "karsi_hesap_prefix": "102", "ic_transfer": True, "banka_adi": "Ziraat"},
            {"tarih": "11.03.2026", "cikis": 30000, "cari_kodu": "320.001",
             "karsi_hesap_prefix": "320", "banka_adi": "Ziraat"},
        ])
        alis = _make_fatura_df([
            {"tarih": "01.03.2026", "cari_kodu": "320.001", "net_tutar": 30000,
             "fatura_turu": "alis"},
        ])
        eslesme = analyze_veri_eslesme(pd.DataFrame(), alis, banka, ANALIZ_AYI)
        self.assertEqual(eslesme.ic_transfer_cikis, 50000)
        self.assertEqual(eslesme.toplam_banka_cikis, 30000)

    def test_120_tahsilat_eslesme(self) -> None:
        cari = "120.01.0014"
        banka = _make_banka_df([
            {"tarih": "05.03.2026", "giris": 75000, "cari_kodu": cari,
             "karsi_hesap_prefix": "120", "banka_adi": "YKB"},
        ])
        satis = _make_fatura_df([
            {"tarih": "05.03.2026", "cari_kodu": cari, "net_tutar": 75000,
             "fatura_turu": "satis"},
        ])
        yas, _ = analyze_reconciliation(
            pd.DataFrame(), pd.DataFrame(), satis, banka, ANALIZ_AYI
        )
        self.assertEqual(yas.toplam_tahsil_edilemeyen, 0)

    def test_infer_ay_from_filename(self) -> None:
        self.assertEqual(infer_ay_from_filename("Alış 032026"), "2026-03")
        self.assertEqual(infer_ay_from_filename("Satış 052026"), "2026-05")
        self.assertIsNone(infer_ay_from_filename("fatura"))

    def test_multi_fatura_merge_filter(self) -> None:
        frames = [
            _make_fatura_df([
                {"tarih": "01.02.2026", "stok_kodu": "A", "net_tutar": 1000,
                 "fatura_turu": "alis", "kaynak_ay": "2026-02", "kaynak_dosya": "Alış 022026.xlsx"},
            ]),
            _make_fatura_df([
                {"tarih": "01.03.2026", "stok_kodu": "B", "net_tutar": 2000,
                 "fatura_turu": "alis", "kaynak_ay": "2026-03", "kaynak_dosya": "Alış 032026.xlsx"},
            ]),
        ]
        merged = pd.concat(frames, ignore_index=True)
        mart = filter_df_by_analiz_ayi(merged, "tarih", ANALIZ_AYI)
        self.assertEqual(len(mart), 1)
        self.assertEqual(float(mart.iloc[0]["net_tutar"]), 2000)

    @unittest.skipUnless(HAM_VERILER.is_dir(), "Ham Veriler klasörü yok")
    def test_ham_veriler_smoke(self) -> None:
        banka_files = [
            HAM_VERILER / "Yapı ve Kredi bankası.xlsx",
            HAM_VERILER / "Ziraat.xlsx",
            HAM_VERILER / "Vakıflar Bankası.xlsx",
        ]
        existing = [p for p in banka_files if p.is_file()]
        self.assertGreater(len(existing), 0, "En az bir banka dosyası bekleniyor")
        banka = load_banka_dosyasi(existing[0])
        self.assertGreater(len(banka), 0)
        self.assertIn("giris", banka.columns)
        self.assertIn("cari_kodu", banka.columns)

        alis_path = HAM_VERILER / "Alış 032026.xlsx"
        satis_path = HAM_VERILER / "Satış 032026.xlsx"
        if alis_path.is_file() and satis_path.is_file():
            alis = load_alis_faturalari_dosyalari([alis_path])
            satis = load_satis_faturalari_dosyalari([satis_path])
            self.assertGreater(len(alis), 0)
            self.assertGreater(len(satis), 0)

    @unittest.skipUnless(DESKTOP_PLAN_120.is_file(), "120.xlsx yok")
    def test_cari_plan_parser_120(self) -> None:
        df = load_tahsilat_plan(DESKTOP_PLAN_120)
        self.assertGreater(len(df), 100)
        self.assertTrue(df["hesap_kodu"].str.startswith("120").all())
        self.assertIn("vade_kalan_gun", df.columns)

    @unittest.skipUnless(DESKTOP_PLAN_320.is_file(), "320.xlsx yok")
    def test_cari_plan_parser_320(self) -> None:
        df = load_tediye_plan(DESKTOP_PLAN_320)
        self.assertGreater(len(df), 50)
        self.assertTrue(df["hesap_kodu"].str.startswith("320").all())

    @unittest.skipUnless(
        DESKTOP_PLAN_120.is_file() and DESKTOP_PLAN_320.is_file(),
        "Plan dosyaları yok",
    )
    def test_cari_plan_analyze_and_vade_net(self) -> None:
        a120 = analyze_cari_plan(load_tahsilat_plan(DESKTOP_PLAN_120))
        a320 = analyze_cari_plan(load_tediye_plan(DESKTOP_PLAN_320))
        self.assertGreater(a120.hesap_sayisi, 0)
        self.assertGreater(a320.hesap_sayisi, 0)
        self.assertGreater(a120.toplam_acik, 0)
        self.assertGreater(a320.toplam_acik, 0)
        vade_net = compute_vade_net(a120, a320)
        self.assertIsNotNone(vade_net)

    @unittest.skipUnless(
        DESKTOP_PLAN_120.is_file() and DESKTOP_PLAN_320.is_file(),
        "Plan dosyaları yok",
    )
    def test_pipeline_with_plans(self) -> None:
        veri = AnalizVeriSeti(
            analiz_ayi=ANALIZ_AYI,
            muavin_df=pd.DataFrame(),
            alis_fatura_df=pd.DataFrame(),
            satis_fatura_df=pd.DataFrame(),
            banka_df=load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv"),
            maas=AylikMaasGirisi(ANALIZ_AYI, []),
            tahsilat_plan_df=load_tahsilat_plan(DESKTOP_PLAN_120),
            tediye_plan_df=load_tediye_plan(DESKTOP_PLAN_320),
        )
        report = run_monthly_analysis(veri)
        self.assertIsNotNone(report.tahsilat_plan)
        self.assertIsNotNone(report.tediye_plan)
        self.assertIsNotNone(report.vade_net)
        self.assertGreater(len(report.cfo_uyarilari.gostergeler), 4)

    def test_monthly_pl(self) -> None:
        muavin = load_muavin(SAMPLES / "ornek_muavin_2026_03.csv")
        alis = _make_fatura_df([
            {"tarih": "01.03.2026", "stok_kodu": "STK1", "net_tutar": 50000, "miktar": 10, "fatura_turu": "alis"},
        ])
        satis = _make_fatura_df([
            {"tarih": "05.03.2026", "stok_kodu": "STK1", "net_tutar": 80000, "miktar": 10,
             "cari_kodu": "120.001", "fatura_turu": "satis"},
        ])
        pl = analyze_monthly_pl(
            ANALIZ_AYI, muavin, alis, satis,
            personel_maaslari=[PersonelMaas("Ali", 0, 10000)],
        )
        self.assertGreater(pl.brut_kar, 0)
        self.assertEqual(pl.toplam_harici_maas, 10000)
        self.assertLess(pl.aylik_net_kar, pl.brut_kar)

    def test_full_pipeline(self) -> None:
        muavin = load_muavin(SAMPLES / "ornek_muavin_2026_03.csv")
        banka = load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv")
        alis = _make_fatura_df([
            {"tarih": "01.03.2026", "stok_kodu": "STK1", "net_tutar": 50000, "miktar": 10,
             "cari_kodu": "320.001", "fatura_turu": "alis"},
        ])
        satis = _make_fatura_df([
            {"tarih": "05.03.2026", "stok_kodu": "STK1", "net_tutar": 80000, "miktar": 10,
             "cari_kodu": "120.001", "fatura_turu": "satis"},
            {"tarih": "20.03.2026", "stok_kodu": "STK2", "net_tutar": 40000, "miktar": 5,
             "cari_kodu": "120.002", "fatura_turu": "satis"},
        ])
        veri = AnalizVeriSeti(
            analiz_ayi=ANALIZ_AYI,
            muavin_df=muavin,
            alis_fatura_df=alis,
            satis_fatura_df=satis,
            banka_df=banka,
            maas=AylikMaasGirisi(ANALIZ_AYI, [PersonelMaas("Ayşe", 15000, 5000)]),
        )
        report = run_monthly_analysis(veri)
        self.assertEqual(report.analiz_ayi, ANALIZ_AYI)
        self.assertIsNotNone(report.cfo_uyarilari)
        self.assertGreater(len(report.cfo_uyarilari.gostergeler), 0)
        self.assertTrue(report.summary_text)

    def test_reconciliation(self) -> None:
        banka = load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv")
        satis = _make_fatura_df([
            {"tarih": "05.03.2026", "stok_kodu": "STK1", "net_tutar": 80000, "miktar": 10,
             "cari_kodu": "120.001", "fatura_turu": "satis"},
        ])
        yas, eslesme = analyze_reconciliation(
            pd.DataFrame(), pd.DataFrame(), satis, banka, ANALIZ_AYI
        )
        self.assertGreaterEqual(yas.toplam_tahsil_edilemeyen, 0)
        self.assertGreaterEqual(eslesme.eslesme_skoru_pct, 0)

    def test_export_smoke(self) -> None:
        muavin = load_muavin(SAMPLES / "ornek_muavin_2026_03.csv")
        veri = AnalizVeriSeti(
            analiz_ayi=ANALIZ_AYI,
            muavin_df=muavin,
            alis_fatura_df=pd.DataFrame(),
            satis_fatura_df=pd.DataFrame(),
            banka_df=load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv"),
            maas=AylikMaasGirisi(ANALIZ_AYI, []),
        )
        report = run_monthly_analysis(veri)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            export_pdf(report, base / "r.pdf")
            export_excel(report, veri, base / "r.xlsx")
            export_word(report, base / "r.docx")
            export_text(report, base / "r.txt")
            for p in base.iterdir():
                self.assertGreater(p.stat().st_size, 0)

    def test_banka_120_giris_excludes_102(self) -> None:
        banka = _make_banka_df([
            {
                "tarih": "05.03.2026", "giris": 10000, "cikis": 0,
                "cari_kodu": "120.001", "karsi_hesap_prefix": "120", "ic_transfer": False,
            },
            {
                "tarih": "06.03.2026", "giris": 5000, "cikis": 0,
                "cari_kodu": "102.001", "karsi_hesap_prefix": "102", "ic_transfer": True,
            },
        ])
        total = banka_120_giris_toplam(banka, ANALIZ_AYI)
        self.assertEqual(total, 10000)

    def test_charts_build_smoke(self) -> None:
        from charts import build_all_charts

        muavin = load_muavin(SAMPLES / "ornek_muavin_2026_03.csv")
        veri = AnalizVeriSeti(
            analiz_ayi=ANALIZ_AYI,
            muavin_df=muavin,
            alis_fatura_df=pd.DataFrame(),
            satis_fatura_df=pd.DataFrame(),
            banka_df=load_banka_dosyasi(SAMPLES / "ornek_banka_2026_03.csv"),
            maas=AylikMaasGirisi(ANALIZ_AYI, []),
        )
        report = run_monthly_analysis(veri)
        charts = build_all_charts(report)
        self.assertIn("nakit", charts)
        self.assertIn("pl", charts)
        self.assertIn("gider", charts)
        self.assertIn("cari", charts)
        self.assertGreaterEqual(len(charts), 4)
        self.assertTrue(report.guvenilirlik_endeks)

    def test_period_utils(self) -> None:
        bas, bit = analiz_ayi_araligi("2026-03")
        self.assertEqual(bas.month, 3)
        self.assertEqual(bit.day, 31)

    def test_ay_karsilastirma(self) -> None:
        alis = _make_fatura_df([
            {"tarih": "01.02.2026", "stok_kodu": "A", "net_tutar": 10000, "fatura_turu": "alis"},
            {"tarih": "01.03.2026", "stok_kodu": "B", "net_tutar": 20000, "fatura_turu": "alis"},
        ])
        satis = _make_fatura_df([
            {"tarih": "05.02.2026", "stok_kodu": "A", "net_tutar": 50000, "fatura_turu": "satis"},
            {"tarih": "05.03.2026", "stok_kodu": "B", "net_tutar": 80000, "fatura_turu": "satis"},
        ])
        banka = _make_banka_df([
            {"tarih": "28.02.2026", "giris": 0, "cikis": 0, "bakiye": 100000},
            {"tarih": "31.03.2026", "giris": 0, "cikis": 0, "bakiye": 150000},
        ])
        veri = AnalizVeriSeti(
            analiz_ayi=ANALIZ_AYI,
            muavin_df=pd.DataFrame(),
            alis_fatura_df=alis,
            satis_fatura_df=satis,
            banka_df=banka,
            maas=AylikMaasGirisi(ANALIZ_AYI, []),
        )
        k = compute_ay_karsilastirma(veri)
        self.assertIsNotNone(k)
        assert k is not None
        self.assertEqual(k.onceki_ayi, "2026-02")
        self.assertEqual(k.brut_kar_fark, k.brut_kar - k.brut_kar_onceki)
        self.assertEqual(k.nakit_sonu_fark, 50000)

    def test_tahsil_edilemeyen_kumulatif_eslesme(self) -> None:
        """Şubat faturası + Şubat tahsilatı; Mart analizinde açık kalmamalı."""
        cari = "120.01.001"
        satis = _make_fatura_df([
            {"tarih": "05.02.2026", "cari_kodu": cari, "net_tutar": 100000, "fatura_turu": "satis"},
        ])
        banka = _make_banka_df([
            {"tarih": "20.02.2026", "giris": 100000, "cari_kodu": cari,
             "karsi_hesap_prefix": "120", "banka_adi": "YKB"},
        ])
        yas, _ = analyze_reconciliation(
            pd.DataFrame(), pd.DataFrame(), satis, banka, ANALIZ_AYI
        )
        self.assertEqual(yas.toplam_tahsil_edilemeyen, 0)

    def test_muavin_eslesme_gider_filtresi(self) -> None:
        muavin = _make_muavin_df([
            {"tarih": "10.03.2026", "hesap_kodu": "100.01", "tl_borc": 30000, "tl_alacak": 0},
            {"tarih": "11.03.2026", "hesap_kodu": "770.01", "tl_borc": 50000, "tl_alacak": 0},
        ])
        banka = _make_banka_df([
            {"tarih": "10.03.2026", "cikis": 30000, "cari_kodu": "320.001",
             "karsi_hesap_prefix": "320", "banka_adi": "Ziraat"},
            {"tarih": "11.03.2026", "cikis": 50000, "cari_kodu": "730.001",
             "karsi_hesap_prefix": "730", "banka_adi": "Ziraat"},
        ])
        eslesme = analyze_veri_eslesme(muavin, pd.DataFrame(), banka, ANALIZ_AYI)
        self.assertEqual(len(eslesme.aciklanamayan_giderler), 1)
        self.assertEqual(eslesme.aciklanamayan_giderler[0].tutar, 30000)
        self.assertGreater(eslesme.eslesen_banka_cikis, 40000)

    def test_plan_mutabakat(self) -> None:
        tahsil_plan = CariPlanSonuc(
            toplam_acik=200000,
            vadesi_gecen=100000,
            vadesi_gelmeyen=100000,
            hesap_sayisi=1,
        )
        tediye_plan = CariPlanSonuc(
            toplam_acik=50000,
            vadesi_gecen=20000,
            vadesi_gelmeyen=30000,
            hesap_sayisi=1,
        )
        yas = YaslandirmaSonuc(
            toplam_tahsil_edilemeyen=80000,
            toplam_odenmeyen=40000,
        )
        sonuc = build_plan_mutabakat(tahsil_plan, tediye_plan, yas)
        self.assertIsNotNone(sonuc)
        assert sonuc is not None
        self.assertEqual(sonuc.tahsilat_fark, 120000)
        self.assertEqual(sonuc.odeme_fark, 10000)
        self.assertGreater(len(sonuc.yorumlar), 1)

    def test_runway_zarar_modu(self) -> None:
        from cashflow_analyzer import NakitAkisOzeti
        from monthly_pl_analyzer import MonthlyPLSonuc
        from reconciliation_analyzer import VeriEslesmeSonuc

        pl = MonthlyPLSonuc(aylik_net_kar=-50000, toplam_operasyonel_gider=100000)
        nakit = NakitAkisOzeti(donem_sonu_net_nakit=150000)
        yas = YaslandirmaSonuc()
        eslesme = VeriEslesmeSonuc()
        cfo = analyze_cfo_uyarilari(pl, nakit, yas, eslesme)
        self.assertEqual(cfo.runway_modu, "zarar")
        self.assertAlmostEqual(cfo.sirket_omru_ay, 3.0)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    if result.result.wasSuccessful():
        print("\nALL TESTS PASSED")
