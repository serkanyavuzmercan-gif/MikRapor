"""
UI smoke testleri — PyQt6 kuruluysa offscreen platformda çalışır, yoksa atlanır.

Amaç piksel doğrulama değil; her rapor görünümünün örnek modelle kurulabildiğini,
ana pencerenin ve ayar diyaloglarının çökmeden oluşturulabildiğini garanti etmek
(CI'da GUI regresyonlarını erken yakalar).
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTreeWidget
    _PYQT = True
except ImportError:
    _PYQT = False


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestUiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    # ------------------------------------------------------------ görünümler
    def test_bilanco_view(self) -> None:
        from domain.mizan_bilanco import build_bilanco
        from ui.bilanco_view import build_bilanco_widget
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 5000.0},
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 1000.0},
        ], asof="2026-06-30")
        w = build_bilanco_widget(b, firma="Test A.Ş.")
        self.assertIsNotNone(w)

    def test_gelir_tablosu_view(self) -> None:
        from domain.gelir_tablosu import build_gelir_tablosu
        from ui.gelir_tablosu_view import build_gelir_tablosu_widget
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 42000.0},
            {"hesap_kodu": "601", "borc": 0.0, "alacak": 8000.0},
            {"hesap_kodu": "621", "borc": 30000.0, "alacak": 0.0},
            {"hesap_kodu": "632", "borc": 6000.0, "alacak": 0.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertIsNotNone(build_gelir_tablosu_widget(gt, firma="Test A.Ş."))

    def test_gelir_tablosu_pastalari(self) -> None:
        """Sağ sütun: gelir/gider halkaları — çizim de dâhil çökmeden kurulmalı."""
        from domain.gelir_tablosu import build_gelir_tablosu, gelir_dagilimi
        from ui.gelir_tablosu_view import _dagilim_sutunu
        from ui.pasta import GELIR_RENKLERI, Halka
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 42000.0},
            {"hesap_kodu": "601", "borc": 0.0, "alacak": 8000.0},
            {"hesap_kodu": "621", "borc": 30000.0, "alacak": 0.0},
            {"hesap_kodu": "632", "borc": 6000.0, "alacak": 0.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertIsNotNone(_dagilim_sutunu(gt))
        h = Halka(gelir_dagilimi(gt), GELIR_RENKLERI)
        h.resize(190, 190)
        h.grab()                                   # paintEvent gerçekten çalışsın
        self.assertGreaterEqual(h._dilim_indeksi(95.0, 20.0), 0)   # en üst dilim
        self.assertEqual(h._dilim_indeksi(95.0, 95.0), -1)         # halkanın deliği

    def test_maliyet_kapanissiz_gider_pastasi_gizlenir(self) -> None:
        """SMM ≈ 0 iken en büyük gider eksik → pasta yanıltır, hiç çizilmez."""
        from domain.gelir_tablosu import build_gelir_tablosu
        from ui.gelir_tablosu_view import _dagilim_sutunu
        gt = build_gelir_tablosu([
            {"hesap_kodu": "600", "borc": 0.0, "alacak": 100000.0},
            {"hesap_kodu": "601", "borc": 0.0, "alacak": 40000.0},
            {"hesap_kodu": "631", "borc": 4000.0, "alacak": 0.0},
            {"hesap_kodu": "632", "borc": 6000.0, "alacak": 0.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertTrue(gt.maliyet_eksik)
        sutun = _dagilim_sutunu(gt)
        basliklar = [w.text() for w in sutun.findChildren(QLabel)]
        self.assertTrue(any("GELİR DAĞILIMI" in b for b in basliklar))
        self.assertFalse(any("GİDER DAĞILIMI" in b for b in basliklar))

    def test_gercek_durum_view(self) -> None:
        from domain.gercek_durum import build_gercek_durum
        from ui.gercek_durum_view import build_gercek_durum_widget
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
        self.assertIsNotNone(build_gercek_durum_widget(gd, firma="Test A.Ş."))

    def test_tahsilat_alacak_view(self) -> None:
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.tahsilat_alacak_view import build_tahsilat_alacak_widget
        ta = build_tahsilat_alacak([
            {"kod": "120.01", "unvan": "Müşteri A", "muh_kod": "120", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 0, "evrak_tarihi": "2026-01-15",
             "cha_vade": "2026-02-15", "tutar": 10000.0, "tutar_donem": 10000.0},
        ], bas="2026-01-01", bit="2026-06-30")
        self.assertIsNotNone(build_tahsilat_alacak_widget(ta, firma="Test A.Ş."))

    def test_gecikmis_borc_da_ustte(self) -> None:
        """
        Gecikmiş alacak KPI'daydı, gecikmiş borç değildi — ikisi birlikte okunur.

        Rakam yaşlandırma panelinde zaten vardı; üstte olmaması onu görünmez kılıyordu.
        """
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.tahsilat_alacak_view import build_tahsilat_alacak_widget
        ta = build_tahsilat_alacak([
            {"kod": "120.01", "unvan": "Müşteri A", "muh_kod": "120", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 0, "evrak_tarihi": "2026-01-15",
             "cha_vade": "2026-02-15", "tutar": 10000.0, "tutar_donem": 10000.0},
            {"kod": "320.01", "unvan": "Satıcı B", "muh_kod": "320", "hareket_tipi": 1,
             "baglanti_tipi": 0, "tip": 1, "evrak_tarihi": "2026-01-10",
             "cha_vade": "2026-02-10", "tutar": 4000.0, "tutar_donem": 4000.0},
        ], bas="2026-01-01", bit="2026-07-29")
        w = build_tahsilat_alacak_widget(ta, firma="Test A.Ş.")
        try:
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            for baslik in ("TOPLAM ALACAK", "GECİKMİŞ ALACAK",
                           "TOPLAM BORÇ", "GECİKMİŞ BORÇ", "NET POZİSYON"):
                self.assertIn(baslik, metinler)
        finally:
            w.deleteLater()

    def test_gerceklesen_etiketi_ve_hareket_sayisi(self) -> None:
        """
        «Bu rakamlar yapılanı değil yapılacak olanı gösteriyor» iddiası doğru DEĞİL.

        Canlıda bir mali müşavir tam olarak bunu söyledi ve rakam savunulamadı. İki
        sebep vardı: «gerçekleşen» kelimesi ekranda hiç geçmiyordu ve dönem toplamı
        tek bir işlem gibi duruyordu. İkisi de başlıkta.
        """
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_view import build_nakit_akis_widget
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-02", "tip": 0, "prefix": "120", "tutar": 7000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0}],
            kapanis_nakit=10000.0, bas="2026-01-01", bit="2026-07-29")
        self.assertEqual((na.giris_adet, na.cikis_adet), (2, 1))
        w = build_nakit_akis_widget(na, firma="Test A.Ş.")
        try:
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            self.assertIn("GERÇEKLEŞEN GİRİŞLER", metinler)
            self.assertIn("GERÇEKLEŞEN ÇIKIŞLAR", metinler)
            self.assertIn("2 hareket", metinler)          # tek işlem değil, toplam
            self.assertIn("01.01–29.07", metinler)
            self.assertIn("dönem TOPLAMIDIR", metinler)
        finally:
            w.deleteLater()

    def test_kategori_satiri_detay_acar(self) -> None:
        """Kanıt bir tık uzakta: satıra tıklayınca arkasındaki fişler istenir."""
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_view import build_nakit_akis_widget
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0}],
            kapanis_nakit=3000.0, bas="2026-01-01", bit="2026-07-29")
        cagri: list[tuple[str, float]] = []
        w = build_nakit_akis_widget(
            na, firma="Test A.Ş.",
            detay_giris=lambda ad, tutar: cagri.append((ad, tutar)))
        try:
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            self.assertIn("arkasındaki fişler açılır", metinler)
            agac = next(a for a in w.findChildren(QTreeWidget)
                        if a.topLevelItem(0)
                        and a.topLevelItem(0).text(0) == "Müşteri tahsilatı")
            agac.itemClicked.emit(agac.topLevelItem(0), 0)
            self.assertEqual(cagri, [("Müşteri tahsilatı", 5000.0)])
            # «Toplam» satırı tıklanınca hiçbir şey açılmaz.
            son = agac.topLevelItem(agac.topLevelItemCount() - 1)
            agac.itemClicked.emit(son, 0)
            self.assertEqual(len(cagri), 1)
        finally:
            w.deleteLater()

    def test_detay_penceresi_mutabakati_yazar(self) -> None:
        """
        Kanıt penceresi kendi rakamını doğrulayamıyorsa hiç olmamasından kötüdür.

        Döküm toplamı panelde yazanla tutmuyorsa bunu SÖYLER; gizlemez.
        Kapanışta çalışan sorgu iptal edilip beklenir — yoksa Qt süreci öldürür.
        """
        from infra.config import MikroConfig
        from ui.nakit_detay_dialog import NakitDetayDialog
        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        satir = [{"tarih": "2026-03-04", "yevmiye": 1201, "hesap": "120.01.0007",
                  "prefix": "120", "tutar": 2_950_000.0}]

        for beklenen, beklenen_metin in ((2_950_000.0, "birebir aynı"),
                                         (3_000_000.0, "fark var")):
            d = NakitDetayDialog(cfg, bas="2026-01-01", bit="2026-07-29", tip=0,
                                 etiket="Müşteri tahsilatı", beklenen=beklenen)
            try:
                d._goster(satir)
                metinler = " ".join(lbl.text() for lbl in d.findChildren(QLabel))
                self.assertIn(beklenen_metin, metinler)
                self.assertIn("1 hareket", metinler)
                self.assertIn("2.950.000,00", metinler)   # biçim bozulmamalı
            finally:
                d.reject()      # çalışan worker'la kapanış: çökmemeli

    def test_sekme_sirasi_sahip_odakli(self) -> None:
        """
        İlk sekme demoyu belirler; Bilanço ile açılmak ürünü muhasebe programı gibi
        gösteriyordu. Resmî tablolar (kural 1b) sona alındı, ayrımın kendisi duruyor.
        """
        from ui.app import MikRaporWindow
        w = MikRaporWindow()
        try:
            adlar = [w._tab_bar.tabText(i).replace("&&", "&")
                     for i in range(w._tab_bar.count())]
            self.assertEqual(adlar[0], "Alacak & Borç")
            self.assertEqual(adlar[1], "Nakit Akış")
            self.assertEqual(adlar[-1], "Yapay Zekâ Yorumu")
            # Resmî ikili sonda ve ayraçlar tam onların iki yanında.
            self.assertEqual(adlar[6:8], ["Bilanço", "Gelir Tablosu"])
            self.assertEqual(w._tab_bar._AYRAC_SONRASI, (5, 7))
            self.assertEqual(w._tab_bar.currentIndex(), 0)
        finally:
            w.close()

    def test_nakit_akis_view(self) -> None:
        from domain.kredi import KrediOdeme
        from domain.nakit_akis import build_nakit_akis
        from domain.tahsilat_alacak import build_tahsilat_alacak
        from ui.nakit_akis_view import _runway_banner, build_nakit_akis_widget
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "320", "tutar": 2000.0},
             {"ay": "2026-01", "tip": 1, "prefix": "300", "tutar": 1000.0}],
            bakiye_kapanis_rows=[{"cins": 2, "borc_h": 10000.0, "alacak_h": 0.0, "ban_hesap_tip": 0}],
            donem_delta=2000.0, bas="2026-01-01", bit="2026-06-30",
        )
        self.assertIsNotNone(build_nakit_akis_widget(
            na,
            firma="Test A.Ş.",
            kredi_odemeleri=[
                KrediOdeme("2026-01-15", "300.01.0001", "Test Bankası Kredisi", 1000.0)
            ],
        ))

        runway_na = build_nakit_akis(
            [
                {"ay": "2026-04", "tip": 0, "prefix": "120", "tutar": 5000.0},
                {"ay": "2026-04", "tip": 1, "prefix": "320", "tutar": 2000.0},
                {"ay": "2026-04", "tip": 1, "prefix": "335", "tutar": 1000.0},
            ],
            kapanis_nakit=10000.0, donem_delta=2000.0,
            bas="2026-04-02", bit="2026-06-30",
        )
        runway_ta = build_tahsilat_alacak([], bas="2026-04-02", bit="2026-06-30")
        self.assertIsNotNone(_runway_banner(
            na, runway_na=runway_na, runway_ta=runway_ta,
            runway_referans_bas="2026-04-02",
        ))

    def test_tahmin_view(self) -> None:
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import build_tahmin_widget
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-06", baslangic_nakit=100000.0, baz_ciro=500000.0,
            buyume_yuzde=2.0, marj_yuzde=20.0, sabit_gider=50000.0, ufuk_ay=6))
        self.assertIsNotNone(build_tahmin_widget(t, firma="Test A.Ş."))

    def test_tahmin_once_normal_sonra_kotu(self) -> None:
        """
        Rapor kötü ihtimalle açılıyordu; işin normal seyrini görmeden felaket
        senaryosu okumak yanlış sırayla düşündürüyor. Grafik artık İKİSİNDE de var.
        """
        import re

        from domain.runway import RunwayTakvim, RunwayTakvimAy
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import build_tahmin_widget
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-08", baslangic_nakit=500000.0, baz_ciro=3000000.0,
            buyume_yuzde=2.0, marj_yuzde=18.0, sabit_gider=400000.0, ufuk_ay=6))
        rt = RunwayTakvim(aylar=[
            RunwayTakvimAy(ay=f"2026-{m:02d}", giren=900000.0, cikan=700000.0,
                           nakit=500000.0) for m in range(8, 12)])
        w = build_tahmin_widget(t, firma="Test A.Ş.", runway=rt)
        try:
            metin = [lbl.text() for lbl in w.findChildren(QLabel)]
            # Bölüm başlığı «— » ile devam eder; kart başlığı «  ·  » ile. İkisi de
            # numaralı olduğu için ayrım buradan yapılır.
            bolum = [m for m in metin if re.match(r"^[①②] .+ — ", m)]
            self.assertEqual(len(bolum), 2)
            self.assertTrue(bolum[0].startswith("① NORMAL BEKLENTİ"))
            self.assertTrue(bolum[1].startswith("② EN KÖTÜ İHTİMAL"))
            # Grafik iki senaryoda da var.
            grafikler = [m for m in metin if "GRAFİĞİ" in m]
            self.assertEqual(len(grafikler), 2)
            self.assertTrue(any("normal beklenti" in g for g in grafikler))
            self.assertTrue(any("en kötü ihtimal" in g for g in grafikler))
            # «Gerçek durum ikisinin arasında olur» tavsiyesi kaldırıldı.
            self.assertFalse(any("arasında" in m for m in metin))
        finally:
            w.deleteLater()

    def test_grafik_en_dusuk_nakiti_isaretler(self) -> None:
        """
        «Grafik başka söylüyor, yazı başka söylüyor» — canlıda birebir bu yaşandı.

        Yazı «2026-08'de nakit eksiye düşüyor (−111.974)» derken grafikte çizgi yalnız
        yukarı gidiyordu: dip, 6,24 milyonluk ölçeğin %1,8'i kadar. Ölçek bozulmadan
        rakam noktanın yanına yazılıyor.
        """
        from ui.tahmin_view import _TahminChart, dip_isareti
        nakit = [-111_974.54, 447_328.32, 1_010_296.19, 6_244_370.70]
        i, etiket = dip_isareti(nakit)
        self.assertEqual(i, 0)
        self.assertIn("111.975", etiket)
        self.assertIn("en düşük", etiket)
        self.assertEqual(dip_isareti([]), (0, ""))

        # Eksili veriyle çizim gerçekten çalışsın (kırmızı parça + işaret).
        c = _TahminChart([(f"2026-{8 + k:02d}", 3.2e6, n) for k, n in enumerate(nakit)])
        c.resize(900, 240)
        c.grab()

    def test_uyari_sonucu_soyler_ve_agirligi_ayirir(self) -> None:
        """Bir ay düşüp toparlamak ile eksi kapatmak aynı uyarıyı almamalı."""
        import re

        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import _nakit_uyarisi, _normal_ozet
        ortak = {"baslangic_ay": "2026-07", "baslangic_nakit": 1_042_810.0,
                 "baz_ciro": 3_234_753.0, "buyume_yuzde": 0.4, "marj_yuzde": 28.1,
                 "sabit_gider": 356_949.0, "ufuk_ay": 12}
        duz = lambda s: re.sub("<[^>]+>", "", s)   # noqa: E731

        # 1) Bir ay dibe iner, toparlar → hafif uyarı, SONUÇ yazılı, sebep söylenmiş.
        t = build_tahmin(TahminVarsayim(**ortak, kart_borcu_acik=1_710_437.0,
                                        kart_borcu_odeme_yuzde=100.0))
        metin, agir = _nakit_uyarisi(t)
        self.assertFalse(agir)
        self.assertIn("sonra toparlıyor", duz(metin))
        self.assertIn("12 ay sonunda", duz(metin))
        self.assertIn("kredi kartı borcu", duz(metin))
        self.assertIn("12 ay sonunda", duz(_normal_ozet(t)))   # önce sonuç

        # 2) Eksi kapatıyor → ağır uyarı.
        kotu = build_tahmin(TahminVarsayim(**{**ortak, "sabit_gider": 1_400_000.0}))
        metin2, agir2 = _nakit_uyarisi(kotu)
        self.assertTrue(agir2)
        self.assertIn("eksi kapatıyor", duz(metin2))

        # 3) Dip yoksa uyarı da yok.
        self.assertEqual(_nakit_uyarisi(build_tahmin(TahminVarsayim(**ortak)))[0], "")

    def test_tahmin_view_nakit_kaynak_uyarisi(self) -> None:
        """Başlangıç nakdi beklenen kaynaktan gelmediyse uyarı görünür, geldiyse görünmez."""
        from PyQt6.QtWidgets import QLabel as _QL

        from domain.nakit_akis import NAKIT_KAYNAK_NOTU
        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import build_tahmin_widget
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-07", baslangic_nakit=0.0, baz_ciro=400_000.0,
            buyume_yuzde=1.0, marj_yuzde=20.0, sabit_gider=60_000.0, ufuk_ay=6))

        def uyari_var(w) -> bool:
            return any("Başlangıç nakdi" in (lb.text() or "")
                       for lb in w.findChildren(_QL))

        self.assertTrue(uyari_var(build_tahmin_widget(t, nakit_notu=NAKIT_KAYNAK_NOTU["yok"])))
        self.assertFalse(uyari_var(build_tahmin_widget(t)), "gl kaynağında uyarı çıkmamalı")

    def test_nakit_notu_elle_girisden_sonra_dusuyor(self) -> None:
        """
        Not DONDURULMAMALI. «Projeksiyon 0 nakitle başlıyor — kendiniz yazın» notu,
        kullanıcı tam bunu yaptıktan sonra ekranda kalıyordu: altındaki projeksiyon
        1,5M'den başlarken not hâlâ 0 diyordu. Ekrandaki rakamla çelişen cümle,
        hiç not olmamasından kötüdür (kural 4).
        """
        from ui.tabs.tahmin_tab import TahminTab
        t = TahminTab.__new__(TahminTab)          # Qt kurulumu olmadan mantığı sına
        t._olculen_nakit = 0.0
        t._nakit_kaynagi = "yok"

        class _Sp:
            def __init__(self, v): self._v = v
            def value(self): return self._v
        t._sp_nakit = _Sp(0.0)
        self.assertTrue(t._nakit_notu(), "ölçülemediğinde sebep yazılmalı")
        self.assertFalse(t._nakit_olculdu())

        t._sp_nakit = _Sp(1_500_000.0)            # kullanıcı kendi yazdı
        self.assertEqual(t._nakit_notu(), "", "elle girişten sonra not düşmeli")
        self.assertTrue(t._nakit_olculdu(), "elle girilen değer ölçülmüş sayılır")

    def test_celiski_notu_kaynak_notunun_onune_gecer(self) -> None:
        """
        Kaynak «gl» olduğu için tek başına sessizdir (NAKIT_KAYNAK_NOTU["gl"] boş),
        ama iki defter bir büyüklük mertebesi ayrışmışsa söylenecek şey vardır.
        """
        from ui.tabs.tahmin_tab import TahminTab
        t = TahminTab.__new__(TahminTab)
        t._olculen_nakit = 514_859.67
        t._nakit_kaynagi = "gl"
        t._nakit_celiski_notu = "Muhasebe kaydı 514.860, banka/kasa hareketleri 25.982.795."

        class _Sp:
            def __init__(self, v): self._v = v
            def value(self): return self._v
        t._sp_nakit = _Sp(514_859.67)
        self.assertEqual(t._nakit_notu(), t._nakit_celiski_notu)

        t._sp_nakit = _Sp(25_982_795.06)          # kullanıcı diğer rakamı yazdı
        self.assertEqual(t._nakit_notu(), "", "elle girişten sonra çelişki notu da düşmeli")

    def test_nakit_olculmediyse_nakit_kartlari_bos(self) -> None:
        """Kural 2: taban ölçülmemişse nakit seviyesi rakamı basılmaz, sebebi yazılır."""
        from PyQt6.QtWidgets import QLabel as _QL

        from domain.tahmin import TahminVarsayim, build_tahmin
        from ui.tahmin_view import build_tahmin_widget
        t = build_tahmin(TahminVarsayim(
            baslangic_ay="2026-07", baslangic_nakit=0.0, baz_ciro=400_000.0,
            buyume_yuzde=1.0, marj_yuzde=20.0, sabit_gider=60_000.0, ufuk_ay=6))

        def metinler(w) -> str:
            return " ".join(lb.text() or "" for lb in w.findChildren(_QL))

        olcusuz = metinler(build_tahmin_widget(t, nakit_olculdu=False))
        self.assertIn("DÖNEM SONU NAKİT", olcusuz)
        self.assertIn("ölçülemedi", olcusuz)
        self.assertIn("—", olcusuz)
        # Akış kartları gerçekten hesaplanıyor, onlar kalmalı (kural 3: gizlemek çare değil)
        self.assertIn("TOPLAM CİRO", olcusuz)
        self.assertIn("TOPLAM NET KÂR", olcusuz)

        olculu = metinler(build_tahmin_widget(t, nakit_olculdu=True))
        self.assertIn("DÖNEM SONU NAKİT", olculu)
        self.assertNotIn("başlangıç nakdi ölçülemedi", olculu)

    def test_reel_deger_view(self) -> None:
        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_view import build_reel_deger_widget
        ta = TahsilatAlacak(
            bas="2026-01-01", bit="2026-07-27",
            acik_vade_parcalari=[
                AcikVadeParcasi("customer", 45, 500_000),
                AcikVadeParcasi("supplier", 60, 300_000),
            ],
        )
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        self.assertIsNotNone(build_reel_deger_widget(a, bas=ta.bas, bit=ta.bit, firma="Test A.Ş."))

    def test_reel_deger_view_basabas_ve_cari_tablolari(self) -> None:
        """Sekmenin boş kalan alt yarısına eklenen bloklar kurulabiliyor mu."""
        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_view import build_reel_deger_widget
        ta = TahsilatAlacak(
            bas="2026-01-01", bit="2026-07-27",
            acik_vade_parcalari=[
                AcikVadeParcasi("customer", 120, 500_000, "M1", "UZUN VADELİ MÜŞTERİ"),
                AcikVadeParcasi("customer", 15, 1_000_000, "M2", "HIZLI ÖDEYEN"),
                AcikVadeParcasi("supplier", 30, 700_000, "S1", "TEDARİKÇİ"),
            ],
        )
        # DSO ölçülmüş hâl: başabaş buna çapalanır
        ta.alacak_toplam, ta.donem_satis, ta.donem_gun = 90.0, 180.0, 180
        ta.alacak_gecikmis = 400_000.0
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        self.assertTrue(a.basabas_olculdu)
        self.assertTrue(a.top_alacak_erime)
        w = build_reel_deger_widget(a, bas=ta.bas, bit=ta.bit, firma="Test A.Ş.")
        self.assertIsNotNone(w)
        metin = " ".join(lb.text() or "" for lb in w.findChildren(QLabel))
        self.assertIn("alt sınır", metin, "gecikmiş alacak alt sınır notu yok")
        # DSO ölçülemeyen hâlde de çökmeden kurulmalı
        ta.donem_satis, ta.donem_gun = 0.0, 0
        a2 = build_reel_deger_analizi(ta, ReelDegerVarsayim(yillik_iskonto_yuzde=45))
        self.assertFalse(a2.basabas_olculdu)
        self.assertIsNotNone(build_reel_deger_widget(a2, bas=ta.bas, bit=ta.bit))

    def test_erime_tablosu_vade_basligi_kirpilmiyor(self) -> None:
        """
        «Vadeye kalan» sütun başlığı «Vadeye ...» diye kesiliyordu — sütun 78px,
        kalın başlık metni ~90px'ti. Sabit genişlik varsayılmasın, ÖLÇÜLSÜN.
        """
        from PyQt6.QtGui import QFont, QFontMetrics
        from PyQt6.QtWidgets import QTreeWidget

        from domain.reel_deger import CariErime
        from ui.reel_deger_view import _erime_tablo
        kayitlar = [CariErime(kod="M1", unvan="TEST FİRMASI A.Ş.", nominal=356_505.54,
                              agirlikli_gun=68.0, vade_etkisi=23_720.19)]
        kart = _erime_tablo(kayitlar, alacak=True)
        agac = kart.findChild(QTreeWidget)
        self.assertIsNotNone(agac)
        f = QFont(self.app.font())
        f.setBold(True)
        gerekli = QFontMetrics(f).horizontalAdvance("Vadeye kalan")
        # QSS padding: 6px 4px → sağ+sol 8px (ui/bilanco_view.py: _TREE_GOVDE)
        self.assertGreaterEqual(agac.columnWidth(2), gerekli + 8,
                                "«Vadeye kalan» başlığı sütuna sığmıyor, kesilir")

    def test_trend_view(self) -> None:
        from domain.gercek_durum import AyTrend
        from domain.mizan_bilanco import build_bilanco
        from domain.trend import build_trend
        from ui.trend_view import build_trend_widget
        b = build_bilanco([
            {"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0},
            {"hesap_kodu": "320", "borc": 0.0, "alacak": 4000.0},
            {"hesap_kodu": "500", "borc": 0.0, "alacak": 6000.0},
        ], asof="2026-06-30")
        tr = build_trend(
            aylik=[AyTrend(ay="2026-01", satis=10000, alis=6000, nakit_giren=8000, nakit_cikan=5000)],
            bilanco=b, bas="2026-01-01", bit="2026-06-30",
        )
        self.assertIsNotNone(build_trend_widget(tr, firma="Test A.Ş."))

    # ------------------------------------------------- pencere ve diyaloglar
    def test_ana_pencere(self) -> None:
        from ui.app import MikRaporWindow
        w = MikRaporWindow()
        try:
            # Sekmeler artık HeaderTabBar (_tab_bar) + QStackedWidget (_stack) ile.
            # 9 RAPOR sekmesi. Veri Sağlığı burada DEĞİL: bütün sekmeler takvime
            # bağlıyken o değil — Mikro Ayarları'ndan açılan bir kontrol penceresi.
            self.assertEqual(w._stack.count(), 9)
            self.assertEqual(w._tab_bar.count(), 9)
        finally:
            w.close()

    def test_tum_sekmeler_gorunur(self) -> None:
        """Hiçbir sekme çubuğu taşmamalı — taşan sekme TIKLANAMAZ, yani rapor kayıptır.

        Regresyon: 8. sekme eklenince «Reel Değer» ve «Mukayese & Oranlar» marka barına
        sığmayıp tamamen görünmez olmuştu (kullanıcı o iki rapora erişemiyordu).

        SIĞMAMA HER ZAMAN HATA DEĞİL: sistem fontu platforma göre değişiyor (ölçüldü,
        Windows Linux'un 1,59 katı) ve 960px'te dokuz sekme orada hiçbir ölçekte
        sığmıyor. Orada doğru davranış etiketi kısaltmaktır. Bu yüzden «kırpılmıyor»
        yalnız kısaltma KAPALIYKEN aranır; her koşulda aranan şey erişilebilirlik.
        Geniş ekranda kısaltma AÇILMAMALI — açılıyorsa ölçüm bozulmuş demektir.
        """
        from PyQt6.QtCore import Qt

        from ui.app import MikRaporWindow
        for genislik in (960, 1220, 1920):  # minimum · varsayılan · tam ekran
            w = MikRaporWindow()
            try:
                w.resize(genislik, 840)
                w.show()
                # Sekme çubuğu genişliğe göre yeniden ölçekleniyor; olay kuyruğu
                # boşalmadan ölçüm alınırsa test ara sıra kırılıyordu (kırılgan).
                for _ in range(12):
                    self.app.sendPostedEvents()
                    self.app.processEvents()
                tb = w._tab_bar
                kisaltiyor = tb.elideMode() != Qt.TextElideMode.ElideNone
                if genislik == 1920:
                    self.assertFalse(
                        kisaltiyor,
                        "1920px'te sekmeler bol bol sığmalı — kısaltma açıksa ölçüm bozuk")
                for i in range(tb.count()):
                    etiket = tb.tabText(i).replace("&&", "&")
                    r = tb.tabRect(i)
                    gerekli = tb._olcu_fontu(tb._font_px).horizontalAdvance(etiket)
                    if kisaltiyor:
                        self.assertGreaterEqual(
                            r.width(), 30,
                            f"{genislik}px pencerede «{etiket}» tıklanamayacak kadar dar")
                    else:
                        self.assertGreaterEqual(
                            r.width(), gerekli,
                            f"{genislik}px pencerede «{etiket}» sekmesi kırpılıyor")
                    self.assertLessEqual(
                        r.right(), tb.width() + 1,
                        f"{genislik}px pencerede «{etiket}» sekmesi taşıyor (görünmez)")
            finally:
                w.close()

    def test_sigmayan_sekme_daraltilir_kaybolmaz(self) -> None:
        """Hiçbir ölçek sığmadığında sekmeler daraltılır — hiçbiri ekran dışında kalmaz.

        BU YOL LINUX'TA KENDİLİĞİNDEN KOŞMAZ: burada dokuz sekme 960px'e rahat sığıyor,
        Windows'ta sığmıyor (sistem fontu 1,59 kat geniş — runner'da ölçüldü). Yalnız
        gerçek pencereye bakan bir test, daraltma kodunun bozulduğunu hiç görmezdi;
        CI yeşil kalır, mağazadaki paket son sekmeyi yutardı. Fontun geniş olduğu
        platform burada TAKLİT edilir.

        `setElideMode` tek başına yetmez — Qt metni sekmenin kendi genişliğine göre
        kısaltır, o genişlik de bizim `tabSizeHint`imizden gelir. Daraltma düşerse bu
        test kırmızıya döner.
        """
        from PyQt6.QtCore import Qt

        from ui.app import HeaderTabBar, MikRaporWindow
        gercek = HeaderTabBar._sekme_genisligi
        HeaderTabBar._sekme_genisligi = (
            lambda self, i, px, dolgu: int(gercek(self, i, px, dolgu) * 1.59))
        try:
            w = MikRaporWindow()
            try:
                w.resize(960, 840)
                w.show()
                for _ in range(12):
                    self.app.sendPostedEvents()
                    self.app.processEvents()
                tb = w._tab_bar
                self.assertEqual(tb.elideMode(), Qt.TextElideMode.ElideRight,
                                 "sığmayan çubukta kısaltma açılmamış")
                self.assertLess(tb._daralma, 1.0, "sekmeler daraltılmamış")
                for i in range(tb.count()):
                    etiket = tb.tabText(i).replace("&&", "&")
                    r = tb.tabRect(i)
                    self.assertLessEqual(r.right(), tb.width() + 1,
                                         f"«{etiket}» ekran dışında kaldı")
                    self.assertGreaterEqual(r.width(), 30,
                                            f"«{etiket}» tıklanamayacak kadar dar")
            finally:
                w.close()
        finally:
            HeaderTabBar._sekme_genisligi = gercek

    def test_mukayese_kutusu_takili_kalmaz(self) -> None:
        """
        «Geçmiş yılların aynı dönemiyle mukayese et» varsayılan KAPALI ve her koşudan
        sonra kapanır.

        Her geçmiş yıl ~5 sorgu demek. İşaret bir kez konulup unutulunca kullanıcı
        istemediği hâlde her rapor dakikalarca sürüyordu; pahalı yol açıkça seçilmeli.
        """
        from infra.config import MikroConfig
        from ui.donem import DonemDurumu
        from ui.tabs.trend_tab import TrendTab
        t = TrendTab(DonemDurumu())
        try:
            self.assertEqual(t.BASLIK, "Mukayese & Oranlar")
            self.assertFalse(t._chk_gecen_yil.isChecked())
            self.assertFalse(t._sp_yil.isEnabled())

            t._chk_gecen_yil.setChecked(True)
            self.assertTrue(t._sp_yil.isEnabled())
            t._sp_yil.setValue(10)
            t._is_hazirla(MikroConfig(), "2026-01-01", "2026-07-28")
            self.assertFalse(t._chk_gecen_yil.isChecked())
        finally:
            t.deleteLater()

    def test_yil_kutusuna_on_yil_geriye_sigar(self) -> None:
        """«10 yıl geriye» yazısı kutuya sığmalı — 112 px sabitlenmişti, kırpıyordu."""
        from ui.donem import DonemDurumu
        from ui.tabs.trend_tab import TrendTab
        t = TrendTab(DonemDurumu())
        try:
            t._sp_yil.setValue(t._sp_yil.maximum())
            metin = f"{t._sp_yil.value()}{t._sp_yil.suffix()}"
            gerekli = t._sp_yil.fontMetrics().horizontalAdvance(metin)
            self.assertGreaterEqual(t._sp_yil.sizeHint().width(), gerekli)
        finally:
            t.deleteLater()

    def test_kdv_paneli_nakit_akista_gorunur(self) -> None:
        """KDV nakit akışın parçası: satışın KDV'si bu ay çıkar, parası aylar sonra girer."""
        from domain.kdv import build_kdv_koprusu
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_view import build_nakit_akis_widget
        na = build_nakit_akis(
            [{"ay": "2026-01", "tip": 0, "tutar": 500_000.0, "prefix": "120"}],
            kapanis_nakit=300_000.0, bas="2026-01-01", bit="2026-03-31")
        kdv = build_kdv_koprusu(
            [{"ay": "2026-01", "hesap": "391", "borc": 0.0, "alacak": 200_000.0},
             {"ay": "2026-01", "hesap": "191", "borc": 120_000.0, "alacak": 0.0}],
            net_satis=1_000_000.0, alacak=1_200_000.0,
            bas="2026-01-01", bit="2026-03-31")
        w = build_nakit_akis_widget(na, firma="Test A.Ş.", kdv=kdv)
        try:
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            self.assertIn("KDV NAKİT KÖPRÜSÜ", metinler)
            self.assertIn("finanse edilir", metinler)
        finally:
            w.deleteLater()

    def test_kdv_okunamadiysa_panel_cizilmez(self) -> None:
        """Boş kart «KDV yükünüz yok» diye okunurdu — okunamayan gösterilmez."""
        from domain.nakit_akis import build_nakit_akis
        from ui.nakit_akis_view import build_nakit_akis_widget
        na = build_nakit_akis([], kapanis_nakit=0.0, bas="2026-01-01", bit="2026-03-31")
        w = build_nakit_akis_widget(na, firma="Test A.Ş.", kdv=None)
        try:
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            self.assertNotIn("KDV NAKİT KÖPRÜSÜ", metinler)
        finally:
            w.deleteLater()

    def test_veri_sagligi_bozuk_kayitlari_listeler(self) -> None:
        """«Düzeltin» tavsiyesi ancak hangi kaydın düzeltileceği yazarsa işe yarar."""
        from domain.veri_sagligi import build_veri_sagligi
        from ui.veri_sagligi_dialog import _kart
        vs = build_veri_sagligi(
            stok_rows=[{"sth_tip": 0, "sth_evraktip": 12, "tutar": 2e7, "adet": 6_592,
                        "aykiri_adet": 1, "aykiri_tutar": 3_333_333_333_340.0}],
            aykiri_rows=[{"tarih": "2023-12-07T00:00:00", "sth_evrakno_seri": "A",
                          "sth_evrakno_sira": 731, "sth_stok_kod": "MAL.001",
                          "sth_tip": 0, "sth_evraktip": 12, "sth_miktar": 2.0,
                          "sth_tutar": 3_333_333_333_340.0}])
        bulgu = next(b for b in vs.bulgular if b.kod == "bozuk_stok")
        kart = _kart(bulgu)
        try:
            metinler = " ".join(lbl.text() for lbl in kart.findChildren(QLabel))
            self.assertIn("2023-12-07", metinler)
            self.assertIn("A731", metinler)
            self.assertIn("MAL.001", metinler)
        finally:
            kart.deleteLater()

    def test_veri_sagligi_butun_gecmisi_tarar(self) -> None:
        """
        Son 12 ay taranıyordu; canlıda 2023'teki 13 bozuk kayıt bu yüzden HİÇ görünmedi.

        Bozuk kayıt mevsimsel değil kalıcıdır ve yılını kapsayan her raporu zehirler —
        «kurulumun hâli» demek kurulumun tamamına bakmak demek. Kapsam katalogtan gelir.
        """
        from datetime import date
        from unittest.mock import patch

        import ui.veri_sagligi_dialog as vsd
        from infra.config import MikroConfig
        from infra.veritabani import FirmaKapsami
        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        gorulen: list[tuple[str, str]] = []

        def sahte_satirlar(_cfg, bas, bit, _cek, **_kw):
            gorulen.append((bas, bit))
            return []

        with patch.object(vsd, "load_config", return_value=cfg), \
             patch.object(vsd, "katalog", return_value=[
                 FirmaKapsami("20", 2019, 2025), FirmaKapsami("26", 2026, 2026)]), \
             patch.object(vsd, "yil_client", return_value=None), \
             patch.object(vsd, "fetch_mizan", return_value=[]), \
             patch.object(vsd, "fetch_firma_adi", return_value="Test A.Ş."), \
             patch.object(vsd, "donem_satirlari", side_effect=sahte_satirlar), \
             patch.object(vsd, "RaporWorker") as sahte_worker:
            d = vsd.VeriSagligiDialog()
            try:
                vs, _firma = sahte_worker.call_args[0][0](lambda _m: None)
            finally:
                d.deleteLater()

        self.assertEqual(gorulen[0][0], "2019-01-01")        # katalogun ilk yılı
        self.assertEqual(gorulen[0][1], date.today().isoformat())
        self.assertEqual(vs.bas, "2019-01-01")
        self.assertEqual(vs.okunamayan, [])

    def test_katalog_okunamazsa_daralma_yazilir(self) -> None:
        """
        Sessizce tek yıla düşmek, temiz sonuca sahte güven verir (kural 2).

        Ama bu bir DÜŞEN KAYNAK DEĞİL: `yil_client` katalog boşken bilerek seçili
        firmayla devam ediyor, mizan ve stok okunuyor. `okunamayan`a yazılınca sonuç
        «kontrol tamamlanamadı» görünüyordu — kural 3b'nin yasakladığı, hiçbir rakamı
        bozmayan uyarı. Kapsam notu olarak kapsam satırında yazar.
        """
        from unittest.mock import patch

        import ui.veri_sagligi_dialog as vsd
        from infra.config import MikroConfig
        cfg = MikroConfig(base_url="https://m.local", api_key="K", firma_kodu="26",
                          calisma_yili=2026, kullanici_kodu="U", sifre_gun="S")
        with patch.object(vsd, "load_config", return_value=cfg), \
             patch.object(vsd, "katalog", return_value=[]), \
             patch.object(vsd, "yil_client", return_value=None), \
             patch.object(vsd, "fetch_mizan", return_value=[]), \
             patch.object(vsd, "fetch_firma_adi", return_value="Test A.Ş."), \
             patch.object(vsd, "donem_satirlari", return_value=[]), \
             patch.object(vsd, "RaporWorker") as sahte_worker:
            d = vsd.VeriSagligiDialog()
            try:
                vs, _firma = sahte_worker.call_args[0][0](lambda _m: None)
            finally:
                d.deleteLater()
        self.assertIn("katalo", vs.kapsam_notu.lower())
        self.assertIn("katalo", vs.kapsam_satiri().lower())
        # Daralan kapsam «düşen kaynak» sayılmaz: okunan neyse temizdir.
        self.assertEqual(vs.okunamayan, [])
        self.assertTrue(vs.temiz)

    def test_tahmin_tazelik_gostergesi(self) -> None:
        """Sağdaki raporun güncel mi bayat mı olduğu panelde yazmalı.

        Hesaplama anlık olduğu için «yükleniyor» göstergesi yanıp söner ve
        kullanıcı rakamların taze olup olmadığını anlayamıyordu.
        """
        from ui.donem import DonemDurumu
        from ui.tabs.tahmin_tab import TahminTab
        t = TahminTab(DonemDurumu())
        try:
            lbl = t._senaryo.lbl_tazelik
            self.assertFalse(lbl.isVisible())  # henüz hesaplanmadı → sessiz
            t._sp_ciro.setValue(1000.0)
            self.assertFalse(lbl.isVisible())  # hesap yokken bayatlık da yok

            t._firma = ""
            t._on_projekte()
            self.assertIn("güncel", lbl.text())

            t._sp_marj.setValue(42.0)
            self.assertIn("değişti", lbl.text())

            t._on_projekte()
            self.assertIn("güncel", lbl.text())
        finally:
            t.close()

    def test_hakkinda_diyalogu(self) -> None:
        from infra.surum import ILETISIM, SURUM, TELIF
        from ui.hakkinda_dialog import HakkindaDialog
        dlg = HakkindaDialog()
        try:
            metinler = " ".join(
                lbl.text() for lbl in dlg.findChildren(QLabel))
            self.assertIn(SURUM, metinler)
            self.assertIn(ILETISIM, metinler)
            self.assertIn(TELIF, metinler)
            self.assertIn("mailto:", metinler)      # hata bildirimi bağlantısı

            dlg._on_kopyala()                        # pano + geri bildirim
            self.assertIn("Kopyalandı", dlg._btn_kopyala.text())
        finally:
            dlg.close()

    def test_ayar_diyaloglari(self) -> None:
        from ui.gercek_durum_settings_dialog import GercekDurumAyarlarDialog
        from ui.mikro_settings_dialog import MikroAyarlarDialog
        MikroAyarlarDialog()
        GercekDurumAyarlarDialog()

    def test_mukayese_karti_tum_satirlari_cizer(self) -> None:
        """Mukayese modele bırakılmaz — kart her koşuda tam çıkmalı."""
        from domain.ai_yorum import YilKapanis, yillar_tablosu
        from ui.mukayese_view import mukayese_karti

        def mk(yil, satis, usd, kur):
            return YilKapanis(
                yil=yil, net_satis=satis, brut_kar=satis * 0.12, net_kar=satis * 0.02,
                smm=-satis * 0.88, stok=140_000.0, alacak=satis * 0.28, donen=satis * 0.38,
                kvyk=satis * 0.4, ozkaynak=satis * 0.15, aktif_toplam=satis * 0.8,
                banka_kredisi=satis * 0.06, satis_usd=usd, kur_son=kur)

        ks = [mk(2021, 20e6, 1_500_430.0, 13.3), mk(2023, 31e6, 1_184_243.0, 27.0),
              mk(2025, 41.2e6, 1_050_163.0, 42.59)]
        kart = mukayese_karti(ks)
        self.assertIsNotNone(kart)
        agac = kart.findChild(QTreeWidget)
        _, bolumler = yillar_tablosu(ks)
        # Yıl başlığı ARTIK SATIR DEĞİL: gerçek header'a taşındı ki tablo aşağı
        # kayarken ekranda kalsın (kullanıcı «başlıklar en üstte sabit kalsın» dedi).
        beklenen = sum(1 + len(b.satirlar) if b.baslik else len(b.satirlar)
                       for b in bolumler)
        self.assertEqual(agac.topLevelItemCount(), beklenen)
        self.assertEqual(agac.columnCount(), 1 + 3 + 1)   # kalem + 3 yıl + değişim
        self.assertFalse(agac.isHeaderHidden())
        basl = agac.headerItem()
        self.assertEqual([basl.text(i) for i in range(1, 5)],
                         ["2021", "2023", "2025", "2025 / önceki ort."])

    def test_elenen_bozuk_kayit_kartta_yazar(self) -> None:
        """Sessizce atılan rakam, yanlış rakamdan iyi değildir — sebebi ekranda."""
        from domain.ai_yorum import YilKapanis
        from ui.mukayese_view import mukayese_karti
        ks = [YilKapanis(yil=y, net_satis=1e6 * y, aktif_toplam=5e5, alacak=2e5,
                         aykiri_adet=2 if y == 2023 else 0,
                         aykiri_tutar=3_333_333_333_340.0 if y == 2023 else 0.0)
              for y in (2023, 2025)]
        kart = mukayese_karti(ks)
        metinler = " ".join(lbl.text() for lbl in kart.findChildren(QLabel))
        self.assertIn("2023", metinler)
        self.assertIn("bozuk stok kaydı toplamdan çıkarıldı", metinler)
        self.assertIn("3.333.333.333.340,00", metinler)

    def test_mukayese_karti_tek_yilda_cizilmez(self) -> None:
        from domain.ai_yorum import YilKapanis
        from ui.mukayese_view import mukayese_karti
        self.assertIsNone(mukayese_karti([YilKapanis(yil=2025)]))
        self.assertIsNone(mukayese_karti([]))

    def test_mukayese_trend_sekmesinde(self) -> None:
        """Tablo API anahtarı gerektirmemeli — Mukayese & Oranlar'da gösterilir."""
        from domain.ai_yorum import YilKapanis
        from domain.gercek_durum import AyTrend
        from domain.mizan_bilanco import build_bilanco
        from domain.trend import build_trend
        from ui.trend_view import build_trend_widget
        b = build_bilanco([{"hesap_kodu": "102", "borc": 10000.0, "alacak": 0.0}],
                          asof="2025-12-31")
        tr = build_trend(
            aylik=[AyTrend(ay="2025-01", satis=10000, alis=6000,
                           nakit_giren=8000, nakit_cikan=5000)],
            bilanco=b, bas="2025-01-01", bit="2025-12-31")
        ks = [YilKapanis(yil=y, net_satis=1e6 * y, aktif_toplam=5e5, alacak=2e5)
              for y in (2024, 2025)]
        w = build_trend_widget(tr, firma="Test A.Ş.", kapanislar=ks)
        try:
            self.assertIsNotNone(w.findChild(QTreeWidget, ))
            metinler = " ".join(lbl.text() for lbl in w.findChildren(QLabel))
            self.assertIn("YILLAR ARASI MUKAYESE", metinler)
        finally:
            w.close()
        # Tek yıl / veri yok: tablo hiç çizilmez.
        w2 = build_trend_widget(tr, firma="Test A.Ş.")
        try:
            metinler = " ".join(lbl.text() for lbl in w2.findChildren(QLabel))
            self.assertNotIn("YILLAR ARASI MUKAYESE", metinler)
        finally:
            w2.close()

    def test_yukleniyor_sure_ipucu_ve_sayac(self) -> None:
        """Yapay zekâ dakikalar sürüyor — «birkaç saniye» demek takıldı hissi veriyordu."""
        from ui.tabs.ai_yorum_tab import AiYorumTab
        from ui.yukleniyor import YukleniyorEkrani

        self.assertIn("dakika", AiYorumTab.SURE_IPUCU)

        y = YukleniyorEkrani(ipucu=AiYorumTab.SURE_IPUCU)
        try:
            self.assertIn("dakika", y._ipucu.text())
            self.assertNotIn("Geçen süre", y._ipucu.text())
            y.basla()
            y._sure_tik()
            self.assertIn("Geçen süre 1 sn", y._ipucu.text())
            for _ in range(60):
                y._sure_tik()
            self.assertIn("Geçen süre 1:01", y._ipucu.text())
            y.durdur()
            self.assertFalse(y._sayac.isActive())   # gizli sekmede CPU yakmasın
            y.basla()
            self.assertNotIn("Geçen süre", y._ipucu.text())   # yeni koşuda sıfırlanır
            y.durdur()
        finally:
            y.close()

    def test_yukleniyor_varsayilan_ipucu(self) -> None:
        from ui.yukleniyor import YukleniyorEkrani
        y = YukleniyorEkrani()
        try:
            self.assertIn("Birkaç saniye", y._ipucu.text())
        finally:
            y.close()

    def test_kaynak_rozeti_tooltip_gostermez(self) -> None:
        from ui.bilesenler import kaynak_rozeti
        rozet = kaynak_rozeti("nakit")
        self.assertIsNotNone(rozet)
        self.assertEqual(rozet.toolTip(), "")


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestSenaryoPaneliKisaEkran(unittest.TestCase):
    """
    Sol senaryo paneli KISA ekranda alanları sıkıştırmamalı.

    Dokuz alan + başlık + buton dikeyde ~680px istiyordu; küçük laptop ekranında
    panele o kadar yer düşmeyince Qt alanları kendi minimumunun altına sıkıştırıyor,
    kutular kısalıp rakamların ALT yarısı kesiliyordu — canlıda "0 TL" → "∩ Tl",
    "12 ay" → "12 av", ondalık virgül tamamen kayboluyordu. Sıkıştırmak yerine
    kaydırılmalı; «Hesapla» da panelin dışına taşmamalı.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from PyQt6.QtWidgets import QSizePolicy

        from ui.bilesenler import para_spin
        from ui.tabs.tahmin_tab import _SenaryoSolPanel

        self._spinler = []
        alanlar = []
        for i in range(9):
            sp = para_spin()
            sp.setMinimumWidth(0)
            sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._spinler.append(sp)
            alanlar.append((f"Alan {i}", sp))
        panel = _SenaryoSolPanel(tuple(alanlar))
        panel.show()
        return panel

    def test_panel_sabit_yukseklik_dayatmaz(self) -> None:
        """Panel «bana 680px ver» demezse pencere kısaldığında içerik bozulmaz."""
        panel = self._panel()
        self.assertLess(
            panel.minimumSizeHint().height(), 400,
            "panel dikeyde sabit bir yükseklik dayatıyor — kısa ekranda içerik sıkışır")

    def test_kisa_ekranda_alanlar_sikismaz(self) -> None:
        panel = self._panel()
        gereken = self._spinler[0].sizeHint().height()
        for h in (620, 460, 400, 340):
            panel.resize(panel.width(), h)
            panel.layout().activate()
            self.app.processEvents()
            for sp in self._spinler:
                self.assertGreaterEqual(
                    sp.height(), gereken,
                    f"panel {h}px iken alan {sp.height()}px'e sıkıştı "
                    f"(gereken {gereken}px) — rakamlar dikeyde kırpılır")

    def test_kisa_ekranda_hesapla_gorunur_kalir(self) -> None:
        panel = self._panel()
        btn = panel.btn_projekte
        for h in (620, 460, 400, 340):
            panel.resize(panel.width(), h)
            panel.layout().activate()
            self.app.processEvents()
            alt = btn.mapTo(panel, btn.rect().bottomLeft()).y()
            self.assertLessEqual(
                alt, h, f"panel {h}px iken «Hesapla» {alt}px'te — panelden taşıyor")

    def test_alanlar_yatayda_paya_sahip(self) -> None:
        """Kaydırma çubuğu çıktığında bile alan istediği genişliği bulmalı."""
        panel = self._panel()
        panel.resize(panel.width(), 400)   # kaydırma çubuğu çıkar
        panel.layout().activate()
        self.app.processEvents()
        sp = self._spinler[0]
        self.assertGreaterEqual(
            sp.width(), sp.sizeHint().width(),
            "alan istediğinden dar çiziliyor — rakamlar yatayda kırpılır")


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestIptalCokmesi(unittest.TestCase):
    """
    İptal, ÇALIŞAN worker'ı silmemeli.

    Çalışan bir QThread'i deleteLater ile yok etmek Qt'de «Destroyed while thread is
    still running» ile süreci öldürür. Eskiden wait(3000) dolduktan sonra deleteLater
    çağrılıyordu; sunucu tarafı 3+ dakika süren bir sorguda İptal'e basınca program
    kapanıyordu. Silmeyi worker'ın kendi `finished` sinyali yapmalı.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        """RaporTab'ın worker yönetimini, ağa çıkmadan, sahte bir worker'la sınar."""
        from ui.rapor_tab import RaporTab

        class SahteWorker:
            def __init__(self) -> None:
                self.iptal_edildi = False
                self.silindi = False
                self.bitti = self.hata = self.ilerleme = _SahteSinyal()

            def iptal_et(self) -> None:
                self.iptal_edildi = True

            def deleteLater(self) -> None:  # noqa: N802 — Qt API
                self.silindi = True

        tab = RaporTab.__new__(RaporTab)      # __init__ widget kurar; gerek yok
        tab._worker = SahteWorker()
        return tab, tab._worker

    def test_calisan_worker_silinmez(self) -> None:
        tab, w = self._tab()
        tab._worker_birak(w)
        self.assertTrue(w.iptal_edildi)
        self.assertFalse(w.silindi)           # ← süreci öldüren çağrı
        self.assertIsNone(tab._worker)

    def test_birakma_ui_threadini_bekletmez(self) -> None:
        """wait() çağrılsaydı sahte worker'da AttributeError patlardı."""
        tab, w = self._tab()
        tab._worker_birak(w)                  # hata vermeden dönmeli


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestYilSagduyusu(unittest.TestCase):
    """
    Tarih kutusuna 7026 yazılınca program uyarmadan kabul ediyordu.

    Sonra 7022-7026 yıllarını veritabanında arıyor, boş bir mukayese tablosu
    üretiyordu (canlıda görüldü). Böyle bir yılda muhasebe kaydı olamaz.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from ui.rapor_tab import RaporTab
        t = RaporTab.__new__(RaporTab)      # __init__ widget kurar; gerek yok
        t._uyarilar = []
        return t

    @staticmethod
    def _tarih(yil: int):
        from PyQt6.QtCore import QDate
        return QDate(yil, 6, 30)

    def _makul_mu(self, yil: int) -> bool:
        from unittest.mock import patch
        with patch("ui.rapor_tab.QMessageBox.warning") as uyari:
            sonuc = self._tab()._yil_makul(self._tarih(yil))
        self.assertEqual(uyari.called, not sonuc)   # ret varsa uyarı da var
        return sonuc

    def test_parmak_hatasi_reddedilir(self) -> None:
        self.assertFalse(self._makul_mu(7026))

    def test_gecmis_yil_kabul_edilir(self) -> None:
        self.assertTrue(self._makul_mu(2021))

    def test_gelecek_yil_kabul_edilir(self) -> None:
        """Gelecek yıla bütçe/plan girilmiş olabilir."""
        from datetime import date
        self.assertTrue(self._makul_mu(date.today().year + 1))

    def test_iki_yil_sonrasi_reddedilir(self) -> None:
        from datetime import date
        self.assertFalse(self._makul_mu(date.today().year + 2))

    def test_cok_eski_yil_reddedilir(self) -> None:
        self.assertFalse(self._makul_mu(1899))


class _SahteSinyal:
    def disconnect(self, *_a) -> None:
        raise TypeError("bağlı değil")        # RaporTab bunu yutmalı


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestEmptyStateOkunabilirlik(unittest.TestCase):
    """
    Hero illüstrasyonu empty-durumda TAM opaklıkla çizilir (soluk mod yalnız rapor
    altındaki arka planda). «ai.png»nin ışıklı AI ikonu marka/başlık/açıklama metninin
    tam arkasına denk gelince okunmuyordu — panel TÜM empty-state'lerde ortak olsun
    diye tek sekmeye özel yama değil, _ClusterPanel'e taşındı.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cluster_kendi_arka_planini_cizer(self) -> None:
        from ui.empty_state import _ClusterPanel, build_empty_state
        w = build_empty_state(
            "Yapay Zekâ Yorumu", "açıklama", cta_hint="Yorumla ve Gönder",
            hero_asset="ai.png", on_cta=lambda: None)
        panel = w.findChild(_ClusterPanel)
        self.assertIsNotNone(panel, "cluster artık kendi arka planını çizen bir panel değil")

    def test_arka_plan_modunda_panel_gizlenir(self) -> None:
        """Rapor altındaki soluk arka planda cluster (ve paneli) hiç görünmemeli."""
        from ui.empty_state import EmptyState
        w = EmptyState("Başlık", "açıklama", hero_asset="ai.png")
        w.set_arka_plan_modu(True)
        self.assertFalse(w._cluster.isVisible())


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestAyarlarTekAdWidget(unittest.TestCase):
    """Düğme metni ile pencere başlığı aynı olmalı (kural 5)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_pencere_basligi_ile_dugme_ayni(self) -> None:
        from ui.app import MikRaporWindow
        from ui.mikro_settings_dialog import AYARLAR_ADI, MikroAyarlarDialog

        w = MikRaporWindow()
        try:
            dugmeler = [b.text().strip() for b in w.findChildren(QPushButton)]
            self.assertIn(AYARLAR_ADI, dugmeler,
                          f"marka barında «{AYARLAR_ADI}» düğmesi yok: {dugmeler}")
            d = MikroAyarlarDialog(w)
            try:
                self.assertEqual(d.windowTitle(), AYARLAR_ADI)
            finally:
                d.deleteLater()
        finally:
            w.close()
            w.deleteLater()


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestSekmeBalonlari(unittest.TestCase):
    """
    Sekme üstüne gelince ne işe yaradığı yazmalı.

    Balon mekanizması (gecikme, kart, «RAPOR» üst etiketi) yazılmıştı ama
    `setTabToolTip` hiç çağrılmadığı için metin boş kalıyor, balon hiç açılmıyordu —
    üstelik `event()` native tooltip'i de bastırdığı için hover'da HİÇBİR ŞEY
    görünmüyordu. 48 satır ölü kod + açıklaması hazır dokuz sekme.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_her_sekmenin_balon_metni_var(self) -> None:
        from ui.app import MikRaporWindow

        w = MikRaporWindow()
        try:
            bar = w._tab_bar
            self.assertGreater(bar.count(), 0)
            for i in range(bar.count()):
                ad = bar.tabText(i).replace("&&", "&")
                tip = bar.tabToolTip(i).strip()
                with self.subTest(sekme=ad):
                    self.assertTrue(tip, f"«{ad}» sekmesinin balon metni boş")
                    # Balon, adı tekrar etmemeli — mekanizma onu zaten eliyor.
                    self.assertNotEqual(tip, ad)
        finally:
            w.close()
            w.deleteLater()


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestBaglantiHatasiSebebi(unittest.TestCase):
    """Rozet «Bağlanılamadı» derken sebebi de taşımalı (kural 2)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_ping_hatasinin_sebebi_kaybolmaz(self) -> None:
        from ui.app import MikRaporWindow

        w = MikRaporWindow()
        try:
            w._on_ping_hata("401 Unauthorized — kullanıcı kodu ya da şifre hatalı")
            self.assertIn("Bağlanılamadı", w._conn.text())
            self.assertIn("şifre hatalı", w._conn_tip._text)
        finally:
            w.close()
            w.deleteLater()

    def test_sebep_bossa_da_bir_sey_yazar(self) -> None:
        from ui.app import MikRaporWindow

        w = MikRaporWindow()
        try:
            w._on_ping_hata("")
            self.assertTrue(w._conn_tip._text.strip())
        finally:
            w.close()
            w.deleteLater()


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestHakkindaKopyala(unittest.TestCase):
    """«Kopyalandı ✓» kalıcı olmamalı — düğmenin ne yaptığını gizliyor."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_etiket_eski_adina_doner(self) -> None:
        """
        Geri alma ZAMANLAYICISININ kurulduğu sınanır, yalnız metodun çalıştığı değil.

        İlk hâlinde test `_kopyala_etiketini_geri_al()`i doğrudan çağırıyordu; o zaman
        `start()` satırı silinse bile test yeşil kalıyordu — kabloyu değil ucu sınamak.
        """
        from ui.hakkinda_dialog import KOPYALA_ETIKET, HakkindaDialog

        d = HakkindaDialog()
        try:
            self.assertEqual(d._btn_kopyala.text(), KOPYALA_ETIKET)
            d._on_kopyala()
            self.assertEqual(d._btn_kopyala.text(), "Kopyalandı ✓")
            self.assertTrue(d._geri_al.isActive(), "geri alma zamanlayıcısı başlamadı")
            # Zamanlayıcıyı beklemeden ateşle — testte 1,8 sn uyumanın anlamı yok.
            d._geri_al.setInterval(0)
            self.app.processEvents()
            self.assertEqual(d._btn_kopyala.text(), KOPYALA_ETIKET)
        finally:
            d.deleteLater()

    def test_zamanlayici_diyaloga_parentli(self) -> None:
        """Pencere kapanınca zamanlayıcı da ölmeli; yoksa silinmiş nesneye setText."""
        from ui.hakkinda_dialog import HakkindaDialog

        d = HakkindaDialog()
        try:
            self.assertIs(d._geri_al.parent(), d)
        finally:
            d.deleteLater()


class TestAyarlarTekAd(unittest.TestCase):
    """
    Aynı ekranın tek adı olur (kural 5). Saf metin taraması — Qt gerektirmez.

    Üç ad birden kullanılıyordu: marka barında «Ayarlar», pencere başlığında «Mikro
    Bağlantı Ayarları», hata metinlerinde «Mikro Ayarları». Kullanıcı «üstteki Mikro
    Ayarları'ndan doldurun» yazısını okuyup o adda bir düğme arıyordu.
    """

    _ESKI_ADLAR = ("Mikro Bağlantı Ayarları", "Mikro bağlantı ayarları")

    @staticmethod
    def _arayuz_metinleri():
        """
        ui/ altındaki KULLANICIYA GİDEN metinler — (dosya, satır, metin).

        Satır bazlı grep YETMEZ: yorumlar ve docstring'ler de eşleşiyor, üstelik bir
        düzeltmeyi anlatan yorum («eskiden «Mikro Bağlantı Ayarları» deniyordu») kendi
        bekçisini kırmızıya düşürüyordu. AST yalnız gerçek dizgileri verir; yorumları
        zaten ayıklar, docstring'leri burada eliyoruz. f-string'lerin sabit parçaları
        da Constant olduğu için kapsama giriyor.
        """
        import ast
        import pathlib

        kok = pathlib.Path(__file__).resolve().parent
        for yol in sorted((kok / "ui").rglob("*.py")):
            agac = ast.parse(yol.read_text(encoding="utf-8"))
            docstringler = set()
            for dugum in ast.walk(agac):
                if not isinstance(dugum, ast.Module | ast.ClassDef
                                  | ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                ilk = next(iter(dugum.body), None)
                if isinstance(ilk, ast.Expr) and isinstance(ilk.value, ast.Constant) \
                        and isinstance(ilk.value.value, str):
                    docstringler.add(id(ilk.value))
            for dugum in ast.walk(agac):
                if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str) \
                        and id(dugum) not in docstringler:
                    yield yol.relative_to(kok), dugum.lineno, dugum.value

    def test_eski_adlar_arayuzde_kalmadi(self) -> None:
        """Kullanıcıya görünen metinlerde eski varyantlar geçmemeli."""
        kirli = [f"{y}:{n}" for y, n, metin in self._arayuz_metinleri()
                 if any(ad in metin for ad in self._ESKI_ADLAR)]
        self.assertEqual(kirli, [], f"eski ayar adı kalmış: {kirli}")

    def test_olmayan_ayara_yonlendirilmiyor(self) -> None:
        """
        «Çalışma yılı» ayarı KALDIRILDI — yıl seçili tarih aralığından türüyor.

        Üç sekmenin «veri bulunamadı» uyarısı kullanıcıyı Mikro Ayarları'nda o adda
        bir alan aramaya gönderiyordu; bulamayınca program bozuk sanılır. (Kural 4'teki
        «Tutarlar TL'dir» notunun aynısı: kaldırılan şeye işaret eden bayat metin.)
        """
        kirli = [f"{y}:{n}" for y, n, metin in self._arayuz_metinleri()
                 if "çalışma yılı" in metin.lower() and "Ayarlar" in metin]
        self.assertEqual(kirli, [], f"olmayan «çalışma yılı» ayarına yönlendirme: {kirli}")


if __name__ == "__main__":
    unittest.main()
