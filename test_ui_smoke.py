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
    from PyQt6.QtWidgets import QApplication, QLabel, QTreeWidget
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
        a = build_reel_deger_analizi(ta, ReelDegerVarsayim(kart_borcu_acik=100_000))
        self.assertIsNotNone(build_reel_deger_widget(a, bas=ta.bas, bit=ta.bit, firma="Test A.Ş."))

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
            # 9 rapor + Veri Sağlığı (rapor değil araç, sonda durur)
            self.assertEqual(w._stack.count(), 10)
            self.assertEqual(w._tab_bar.count(), 10)
            self.assertEqual(w._tab_bar.tabText(9), "Veri Sağlığı")
        finally:
            w.close()

    def test_tum_sekmeler_gorunur(self) -> None:
        """Her sekme etiketi tam sığmalı — hiçbiri kırpılmamalı/taşmamalı.

        Regresyon: 8. sekme eklenince «Reel Değer» ve «Trend & Oranlar» marka barına
        sığmayıp tamamen görünmez olmuştu (kullanıcı o iki rapora erişemiyordu).
        Yeni sekme eklenirse bu test dar pencerede de uyarır.
        """
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
                for i in range(tb.count()):
                    etiket = tb.tabText(i).replace("&&", "&")
                    r = tb.tabRect(i)
                    gerekli = tb._olcu_fontu(tb._font_px).horizontalAdvance(etiket)
                    self.assertGreaterEqual(
                        r.width(), gerekli,
                        f"{genislik}px pencerede «{etiket}» sekmesi kırpılıyor")
                    self.assertLessEqual(
                        r.right(), tb.width() + 1,
                        f"{genislik}px pencerede «{etiket}» sekmesi taşıyor (görünmez)")
            finally:
                w.close()

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
        beklenen = 1 + sum(1 + len(b.satirlar) if b.baslik else len(b.satirlar)
                           for b in bolumler)
        self.assertEqual(agac.topLevelItemCount(), beklenen)
        self.assertEqual(agac.columnCount(), 1 + 3 + 1)   # kalem + 3 yıl + değişim
        self.assertEqual(agac.topLevelItem(0).text(4), "2021→2025")

    def test_mukayese_karti_tek_yilda_cizilmez(self) -> None:
        from domain.ai_yorum import YilKapanis
        from ui.mukayese_view import mukayese_karti
        self.assertIsNone(mukayese_karti([YilKapanis(yil=2025)]))
        self.assertIsNone(mukayese_karti([]))

    def test_mukayese_trend_sekmesinde(self) -> None:
        """Tablo API anahtarı gerektirmemeli — Trend & Oranlar'da gösterilir."""
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


if __name__ == "__main__":
    unittest.main()
