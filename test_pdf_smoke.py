"""
PDF dışa aktarım smoke testleri — reportlab kuruluysa çalışır, yoksa atlanır.

Amaç derin doğrulama değil; PDF üretiminin uçtan uca patlamadığını ve geçerli
bir PDF dosyası (%PDF imzalı, boş olmayan) yazdığını garanti etmek.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import reportlab  # noqa: F401
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False

from domain.gelir_tablosu import build_gelir_tablosu
from domain.mizan_bilanco import build_bilanco

_MIZAN_ROWS = [
    {"hesap_kodu": "100", "borc": 500.0, "alacak": 0.0},
    {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
    {"hesap_kodu": "120", "borc": 5000.0, "alacak": 0.0},
    {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
    {"hesap_kodu": "500", "borc": 0.0, "alacak": 10000.0},
    {"hesap_kodu": "600", "borc": 0.0, "alacak": 1500.0},
]

_GT_ROWS = [
    {"hesap_kodu": "600", "borc": 0.0, "alacak": 42000.0},
    {"hesap_kodu": "610", "borc": 2000.0, "alacak": 0.0},
    {"hesap_kodu": "621", "borc": 30000.0, "alacak": 0.0},
    {"hesap_kodu": "632", "borc": 4000.0, "alacak": 0.0},
    {"hesap_kodu": "660", "borc": 500.0, "alacak": 0.0},
]


def _pdf_dogrula(tc: unittest.TestCase, path: Path) -> None:
    tc.assertTrue(path.is_file())
    data = path.read_bytes()
    tc.assertGreater(len(data), 1000, "PDF şüpheli derecede küçük")
    tc.assertTrue(data.startswith(b"%PDF"), "geçerli PDF imzası yok")


@unittest.skipUnless(_REPORTLAB, "reportlab kurulu değil")
class TestPdfSmoke(unittest.TestCase):
    def test_bilanco_pdf(self) -> None:
        from ui.bilanco_pdf import export_bilanco_pdf
        b = build_bilanco(_MIZAN_ROWS, asof="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bilanco.pdf"
            export_bilanco_pdf(
                b, out, firma="Test Ticaret A.Ş.",
                bas="2026-01-01", bit="2026-06-30",
            )
            _pdf_dogrula(self, out)

    def test_gelir_tablosu_pdf(self) -> None:
        from ui.gelir_tablosu_pdf import export_gelir_tablosu_pdf
        gt = build_gelir_tablosu(_GT_ROWS, bas="2026-01-01", bit="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gelir_tablosu.pdf"
            export_gelir_tablosu_pdf(gt, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_gercek_durum_pdf(self) -> None:
        from domain.gercek_durum import build_gercek_durum
        from ui.gercek_durum_pdf import export_gercek_durum_pdf
        gd = build_gercek_durum(
            stok_rows=[
                {"sth_tip": 1, "sth_evraktip": 4, "tutar": 42000.0, "miktar": 10, "adet": 3},
                {"sth_tip": 0, "sth_evraktip": 3, "tutar": 30000.0, "miktar": 8, "adet": 2},
            ],
            stok_aylik=[{"ay": "2026-01", "sth_tip": 1, "sth_evraktip": 4, "tutar": 42000.0}],
            nakit_rows=[{"giren": 50000.0, "cikan": 30000.0}],
            nakit_aylik=[{"ay": "2026-01", "giren": 50000.0, "cikan": 30000.0}],
            bas="2026-01-01", bit="2026-06-30",
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "gercek_durum.pdf"
            export_gercek_durum_pdf(gd, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_nakit_akis_pdf(self) -> None:
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_pdf import export_nakit_akis_pdf
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0}],
            bakiye_kapanis_rows=[{"cins": 2, "borc_h": 10000.0, "alacak_h": 0.0, "ban_hesap_tip": 0}],
            donem_delta=3000.0, bas="2026-01-01", bit="2026-06-30",
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "nakit_akis.pdf"
            export_nakit_akis_pdf(na, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_tahsilat_alacak_pdf(self) -> None:
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.tahsilat_alacak_pdf import export_tahsilat_alacak_pdf
        ta = build_tahsilat_alacak([
            {"kod": "120.01", "unvan": "Müşteri A", "muh_kod": "120", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 0, "evrak_tarihi": "2026-01-15",
             "cha_vade": "2026-02-15", "tutar": 10000.0, "tutar_donem": 10000.0},
        ], bas="2026-01-01", bit="2026-06-30")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "tahsilat.pdf"
            export_tahsilat_alacak_pdf(ta, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_tahmin_pdf(self) -> None:
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_pdf import export_tahmin_pdf
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-06", baslangic_nakit=100000.0, baz_ciro=500000.0,
            buyume_yuzde=2.0, marj_yuzde=20.0, sabit_gider=50000.0,
            kart_borcu_acik=250000.0, kart_borcu_odeme_yuzde=25.0, ufuk_ay=6))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "tahmin.pdf"
            export_tahmin_pdf(t, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_reel_deger_pdf(self) -> None:
        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_pdf import export_reel_deger_pdf
        ta = TahsilatAlacak(
            bas="2026-01-01", bit="2026-07-27",
            acik_vade_parcalari=[
                AcikVadeParcasi("customer", 120, 500_000, "M1", "UZUN VADELİ MÜŞTERİ"),
                AcikVadeParcasi("customer", 15, 1_000_000, "M2", "HIZLI ÖDEYEN"),
                AcikVadeParcasi("supplier", 30, 700_000, "S1", "TEDARİKÇİ"),
            ],
        )
        ta.vade_kaynagi = "vade"
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reel_deger.pdf"
            export_reel_deger_pdf(a, out, bas=ta.bas, bit=ta.bit, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_reel_deger_pdf_vade_olculemezse(self) -> None:
        """Makas gösterilmediğinde de PDF üretilmeli (kural 2: sebebi yazılır)."""
        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_pdf import export_reel_deger_pdf
        ta = TahsilatAlacak(bas="2026-01-01", bit="2026-07-27", acik_vade_parcalari=[
            AcikVadeParcasi("customer", 90, 400_000, "M1", "MÜŞTERİ")])
        ta.vade_kaynagi = "tarih"
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reel_deger_tahmini.pdf"
            export_reel_deger_pdf(a, out, bas=ta.bas, bit=ta.bit)
            _pdf_dogrula(self, out)

    def test_trend_pdf(self) -> None:
        from domain.gercek_durum import AyTrend
        from domain.trend import build_trend
        from ui.trend_pdf import export_trend_pdf
        b = build_bilanco(_MIZAN_ROWS, asof="2026-06-30")
        tr = build_trend(
            aylik=[AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000)],
            bilanco=b, bas="2026-01-01", bit="2026-06-30",
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "trend.pdf"
            export_trend_pdf(tr, out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)


@unittest.skipUnless(_REPORTLAB, "reportlab kurulu değil")
class TestVeriSagligiPdf(unittest.TestCase):
    """
    Bu PDF MALİ MÜŞAVİRE gidiyor: «şu kayıtları düzeltir misin» diye.

    O yüzden iki şey şart — düzeltilecek kayıtların TAMAMI (ekranda ilk 12 gösteriliyor,
    burada kırpma yok) ve neyin tarandığı (kapsam yazmazsa «temiz» sonucu sahte güven
    verir).
    """

    @staticmethod
    def _vs(kayit_adet: int = 30):
        from domain.veri_sagligi import build_veri_sagligi
        return build_veri_sagligi(
            bas="2019-01-01", bit="2026-07-28",
            stok_rows=[{"sth_tip": 0, "sth_evraktip": 12, "tutar": 2e7, "adet": 6_592,
                        "aykiri_adet": kayit_adet, "aykiri_tutar": 3_333_333_333_340.0}],
            aykiri_rows=[{"tarih": "2023-12-07T00:00:00", "sth_evrakno_seri": "A",
                          "sth_evrakno_sira": 700 + i, "sth_stok_kod": f"MAL.{i:03d}",
                          "sth_tip": 0, "sth_evraktip": 12, "sth_miktar": 2.0,
                          "sth_tutar": 3_333_333_333_340.0}
                         for i in range(kayit_adet)])

    def test_pdf_uretilir(self) -> None:
        from ui.veri_sagligi_pdf import export_veri_sagligi_pdf
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "veri_sagligi.pdf"
            export_veri_sagligi_pdf(self._vs(), out, firma="Test Ticaret A.Ş.")
            _pdf_dogrula(self, out)

    def test_temiz_veride_de_uretilir(self) -> None:
        """
        Bulgu yoksa da belge çıkmalı: «kontrol edildi, temiz» de bir sonuçtur.

        «Temiz» için İKİ kaynağın da okunmuş olması şart — `bilanco` verilmeyince
        mizan okunamamış sayılır ve sonuç temiz değildir.
        """
        from domain.mizan_bilanco import build_bilanco
        from domain.veri_sagligi import build_veri_sagligi
        from ui.veri_sagligi_pdf import export_veri_sagligi_pdf
        # Dengeli mizan: aktif 900.000 = pasif 700.000 + dönem kârı 200.000. 621
        # işlenmiş olmalı, yoksa maliyet bulgusu çıkar ve sonuç «temiz» olmaz.
        bilanco = build_bilanco(
            [{"hesap_kodu": "102", "borc": 100_000.0, "alacak": 0.0},
             {"hesap_kodu": "153", "borc": 800_000.0, "alacak": 0.0},
             {"hesap_kodu": "320", "borc": 0.0, "alacak": 300_000.0},
             {"hesap_kodu": "500", "borc": 0.0, "alacak": 400_000.0},
             {"hesap_kodu": "600", "borc": 0.0, "alacak": 900_000.0},
             {"hesap_kodu": "621", "borc": 700_000.0, "alacak": 0.0}],
            asof="2026-07-28")
        vs = build_veri_sagligi(bas="2026-01-01", bit="2026-07-28",
                                bilanco=bilanco, stok_rows=[])
        self.assertTrue(vs.temiz)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "temiz.pdf"
            export_veri_sagligi_pdf(vs, out)
            _pdf_dogrula(self, out)

    def test_kayitlar_kirpilmadan_girer(self) -> None:
        """Ekran ilk 12'yi gösteriyor; müşavire eksik liste gönderilemez."""
        from ui.veri_sagligi_pdf import _kayit_tablosu
        bulgu = next(b for b in self._vs(30).bulgular if b.kod == "bozuk_stok")
        self.assertEqual(len(bulgu.kayitlar), 30)
        t = _kayit_tablosu(bulgu.kayitlar)
        self.assertEqual(len(t._cellvalues), 31)      # 1 başlık + 30 kayıt


@unittest.skipUnless(_REPORTLAB, "reportlab kurulu değil")
class TestMukayesePdfSigar(unittest.TestCase):
    """
    Mukayese tablosu SAYFAYA SIĞMALI.

    Kullanıcı «trend&oranlar pdf sığmıyor» dedi: on yıl istendiğinde sütun 11 mm'ye
    düşüyor, «41,2 milyon» komşu hücrenin üstüne biniyordu. reportlab düz metin
    hücresini kırpmaz, taşırır — yani bozukluk sessizdir. Bu test her hücrenin kendi
    sütununa GERÇEKTEN sığdığını ölçer.
    """

    @staticmethod
    def _kapanislar(n: int) -> list:
        from domain.ai_yorum import YilKapanis
        return [YilKapanis(
            yil=y, net_satis=41_200_000.0, brut_kar=5_000_000.0, net_kar=1_000_000.0,
            faaliyet_kari=2_000_000.0, smm=-36_000_000.0, stok=1_400_000.0,
            alacak=11_000_000.0, alacak_gecikmis=7_600_000.0, borc=5_000_000.0,
            donen=20_000_000.0, kvyk=16_000_000.0, uvyk=2_000_000.0,
            ozkaynak=6_000_000.0, aktif_toplam=32_000_000.0,
            banka_kredisi=2_400_000.0, finansman_gideri=-800_000.0,
            faaliyet_gideri=-3_000_000.0, fiili_satis=40_000_000.0,
            fiili_alis=35_000_000.0, fiili_var=True,
            satis_usd=1_050_163.0 + y, kur_son=13.3 + (y - 2016), kur_ort=12.0 + (y - 2016),
        ) for y in range(2026 - n, 2026)]

    def _tasan(self, n_yil: int) -> list[str]:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics

        from ui.mukayese_pdf import _PADDING, _genislikler, yazi_boyu
        from ui.pdf_ortak import FONT_B

        en = landscape(A4)[0] - 36 * mm       # pdf_doc kenar boşlukları
        genislik, yil_en = _genislikler(en, n_yil)
        punto = yazi_boyu(yil_en)
        tablo = _mukayese_data(self._kapanislar(n_yil))
        tasan = []
        for satir in tablo:
            for i, hucre in enumerate(satir):
                if not hucre:
                    continue
                # Kalın ölçülür: değişim ve başlık hücreleri kalın, en geniş hâli budur.
                w = pdfmetrics.stringWidth(str(hucre), FONT_B, punto)
                if w > genislik[i] - 2 * _PADDING:
                    tasan.append(f"{n_yil} yıl · sütun {i}: {hucre!r} "
                                 f"{w / mm:.1f}mm > {(genislik[i] - 2 * _PADDING) / mm:.1f}mm")
        return tasan

    def test_iki_yildan_on_yila_kadar_tasma_yok(self) -> None:
        for n in (2, 3, 5, 8, 10):
            with self.subTest(yil=n):
                self.assertEqual(self._tasan(n), [])


def _mukayese_data(kapanislar: list) -> list[list[str]]:
    """mukayese_tablosu'nun ürettiği hücre matrisi (ölçüm için yeniden kurulur)."""
    from domain.ai_yorum import degisim_basligi, ortak_pencere, yillar_tablosu
    yillar, bolumler = yillar_tablosu(kapanislar)
    ortak = ortak_pencere(kapanislar)

    def _bas(yil: int) -> str:
        if ortak:
            return str(yil)
        k = next((x for x in kapanislar if x.yil == yil), None)
        return k.basligi() if k is not None else str(yil)

    data = [[""] + [_bas(y) for y in yillar] + [degisim_basligi(yillar)]]
    for bolum in bolumler:
        for satir in bolum.satirlar:
            data.append([satir.etiket, *satir.hucreler, satir.degisim])
    return data


# Muhasebeci elle giriyor: ünvanların ve stok kodlarının «temiz» olduğu VARSAYILMAZ.
_KOTU_AD = "A<B & C>D SAN. TİC. LTD.ŞTİ."


@unittest.skipUnless(_REPORTLAB, "reportlab kurulu değil")
class TestSerbestMetinKacisi(unittest.TestCase):
    """
    Veritabanından gelen serbest metin PDF'i ÇÖKERTMEZ.

    `Paragraph` içeriğini mini-HTML gibi ayrıştırır; firma adında ya da cari ünvanında
    tek bir «<» bütün belgeyi `paraparser: syntax error: parse ended with 2 unclosed
    tags` ile düşürüyordu — kullanıcıya hiçbir şey söylemeyen bir hatayla. «&»
    reportlab tarafından affediliyordu, «<» affedilmiyordu.

    Firma adı DOKUZ PDF'in hepsine `letterhead_sade` üzerinden giriyor; bu yüzden test
    üreticileri tek tek değil TOPLUCA koşturur — yeni bir rapor eklendiğinde de aynı
    kapıdan geçtiği sürece korunur.
    """

    def _uret(self, ad: str, cagir) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / f"{ad}.pdf"
            cagir(out)
            _pdf_dogrula(self, out)

    def test_firma_adindaki_isaretler_dokuz_pdfi_dusurmez(self) -> None:
        from domain.gercek_durum import build_gercek_durum
        from domain.nakit_akis import build_nakit_akis
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from domain.trend import build_trend
        from ui.bilanco_pdf import export_bilanco_pdf
        from ui.gelir_tablosu_pdf import export_gelir_tablosu_pdf
        from ui.gercek_durum_pdf import export_gercek_durum_pdf
        from ui.nakit_akis_pdf import export_nakit_akis_pdf
        from ui.tahsilat_alacak_pdf import export_tahsilat_alacak_pdf
        from ui.trend_pdf import export_trend_pdf

        b = build_bilanco(_MIZAN_ROWS, asof="2026-06-30")
        gt = build_gelir_tablosu(_GT_ROWS, bas="2026-01-01", bit="2026-06-30")
        na = build_nakit_akis([{"ay": "2026-01", "tip": 0, "prefix": "120",
                                "tutar": 5000.0}],
                              kapanis_nakit=10_000.0, donem_delta=1000.0,
                              bas="2026-01-01", bit="2026-06-30")
        ta = build_tahsilat_alacak([], bas="2026-01-01", bit="2026-06-30")
        gd = build_gercek_durum(stok_rows=[], stok_aylik=[], nakit_rows=[],
                                nakit_aylik=[], bas="2026-01-01", bit="2026-06-30")
        tr = build_trend(bilanco=b, aylik=[], bas="2026-01-01", bit="2026-06-30")

        uretimler = {
            "bilanco": lambda o: export_bilanco_pdf(
                b, o, firma=_KOTU_AD, bas="2026-01-01", bit="2026-06-30"),
            "gelir": lambda o: export_gelir_tablosu_pdf(gt, o, firma=_KOTU_AD),
            "nakit": lambda o: export_nakit_akis_pdf(na, o, firma=_KOTU_AD),
            "tahsilat": lambda o: export_tahsilat_alacak_pdf(ta, o, firma=_KOTU_AD),
            "gercek": lambda o: export_gercek_durum_pdf(gd, o, firma=_KOTU_AD),
            "trend": lambda o: export_trend_pdf(tr, o, firma=_KOTU_AD),
        }
        for ad, cagir in uretimler.items():
            with self.subTest(rapor=ad):
                self._uret(ad, cagir)

    def test_cari_unvanindaki_isaretler_reel_degeri_dusurmez(self) -> None:
        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_pdf import export_reel_deger_pdf

        ta = TahsilatAlacak(bas="2026-01-01", bit="2026-07-30",
                            acik_vade_parcalari=[
                                AcikVadeParcasi("customer", 60, 500_000.0, "M1",
                                                _KOTU_AD)])
        ta.alacak_toplam, ta.donem_satis, ta.donem_gun = 500_000.0, 2_000_000.0, 211
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        self.assertTrue(a.top_alacak_erime, "test ünvanı listeye girmedi")
        self._uret("reel", lambda o: export_reel_deger_pdf(
            a, o, bas=ta.bas, bit=ta.bit, firma=_KOTU_AD))

    def test_stok_kodundaki_isaretler_veri_sagligini_dusurmez(self) -> None:
        """«Düzeltilecek kayıtlar» satırları Mikro'dan gelen stok kodunu taşıyor."""
        from domain.veri_sagligi import build_veri_sagligi
        from ui.veri_sagligi_pdf import export_veri_sagligi_pdf

        vs = build_veri_sagligi(
            bas="2019-01-01", bit="2026-07-28",
            stok_rows=[{"sth_tip": 0, "sth_evraktip": 12, "tutar": 2e7, "adet": 6_592,
                        "aykiri_adet": 1, "aykiri_tutar": 3_333_333_333_340.0}],
            aykiri_rows=[{"tarih": "2023-12-07T00:00:00", "sth_evrakno_seri": "A<B",
                          "sth_evrakno_sira": 700, "sth_stok_kod": "MAL<001>",
                          "sth_tip": 0, "sth_evraktip": 12, "sth_miktar": 2.0,
                          "sth_tutar": 3_333_333_333_340.0}])
        kayit = next(b for b in vs.bulgular if b.kayitlar).kayitlar[0]
        self.assertIn("<", kayit, "test verisi işaret taşımıyor")
        self._uret("saglik", lambda o: export_veri_sagligi_pdf(vs, o, firma=_KOTU_AD))

    def test_pdf_metin_isaretleri_kacislar(self) -> None:
        from ui.pdf_ortak import pdf_metin
        self.assertEqual(pdf_metin("A<B>C&D"), "A&lt;B&gt;C&amp;D")
        self.assertEqual(pdf_metin(None), "")


if __name__ == "__main__":
    unittest.main()
