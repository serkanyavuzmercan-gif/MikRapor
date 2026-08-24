"""Arkadaş demosunun bekçileri — üç ekran düzeltmesi geri gelmesin.

test_ui_smoke.py'den ayrı dosyada: sınıf kendi başına ayakta durur ve smoke
dosyasını büyütmez. Aynı koşullarda (PyQt6 + offscreen) koşar.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _PYQT = True
except ImportError:
    _PYQT = False


@unittest.skipUnless(_PYQT, "PyQt6 kurulu değil")
class TestDemoGeriBildirimi(unittest.TestCase):
    """
    Arkadaş demosunun bekçileri — üç ekran düzeltmesi geri gelmesin.

    Kullanıcı programı bir arkadaşına gösterdi ve üç yapısal kusur bildirdi:
    mukayese en altta bulunamıyor, ayarlar formunda «Yılları Tara» bağlantı
    alanlarından önce, Reel Değer hero'su panellerin birebir tekrarı.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_mukayese_karti_oranlardan_once(self) -> None:
        """Sekmenin adı «Mukayese & Oranlar» — mukayese ilk bakışta görünmeli."""
        from domain.ai_yorum import YilKapanis
        from domain.mizan_bilanco import Bilanco, BilancoSatir
        from domain.trend import build_trend
        from ui.trend_view import build_trend_widget

        b = Bilanco(asof="2026-07-31")
        b.aktif = [BilancoSatir("100", "Kasa", 1000.0)]
        b.pasif = [BilancoSatir("500", "Sermaye", 1000.0)]
        b.aktif_toplam = 1000.0
        tr = build_trend(bilanco=b, bas="2026-01-01", bit="2026-07-31")
        kapanislar = [YilKapanis(yil=2025, net_satis=100.0),
                      YilKapanis(yil=2026, net_satis=120.0)]
        w = build_trend_widget(tr, kapanislar=kapanislar)
        try:
            lay = w.layout()
            adlar = []
            for i in range(lay.count()):
                item = lay.itemAt(i).widget()
                adlar.append(item.objectName() if item is not None else "(layout)")
            self.assertIn("mukayeseKarti", adlar)
            # Mukayese, oran/bilanço satırından (isimsiz layout) önce gelmeli.
            self.assertLess(adlar.index("mukayeseKarti"), adlar.index("(layout)"),
                            f"mukayese kartı en üstte değil: {adlar}")
        finally:
            w.deleteLater()

    def test_ayarlarda_yillari_tara_baglanti_alanlarindan_sonra(self) -> None:
        """
        «Yılları Tara» bağlantı İSTER; şifreden önce dururken kullanıcı ona boş
        formla basıyor ve düğmeyi bozuk sanıyordu (canlı demo). Odak düzeni
        (sekmeyle gezinme sırası = ekleme sırası) bunu sınar.
        """
        from ui.mikro_settings_dialog import MikroAyarlarDialog

        d = MikroAyarlarDialog()
        try:
            form = d._sifre_gun.parentWidget().layout()
            sira = {}
            for i in range(form.count()):
                w = form.itemAt(i).widget()
                if w is d._sifre_gun:
                    sira["sifre"] = i
                if w is d._btn_katalog or (w is not None and w.layout() is not None):
                    pass
            # Yerleşim iç içe olabilir — koordinatla sınamak daha sağlam:
            d.adjustSize()
            self.assertLess(d._sifre_gun.y(), d._btn_katalog.y(),
                            "«Yılları Tara» hâlâ şifre alanının üstünde")
            self.assertLess(d._kullanici.y(), d._btn_katalog.y())
        finally:
            d.deleteLater()

    def test_reel_deger_herosu_panellerin_tekrari_degil(self) -> None:
        """Hero üç TÜREV rakam gösterir; nominal/bugünkü değer yalnız panellerde."""
        from PyQt6.QtWidgets import QLabel

        from domain.reel_deger import ReelDegerVarsayim, build_reel_deger_analizi
        from domain.tahsilat_alacak import AcikVadeParcasi, TahsilatAlacak
        from ui.reel_deger_view import build_reel_deger_widget

        ta = TahsilatAlacak(bas="2026-01-01", bit="2026-07-31")
        ta.acik_vade_parcalari = [
            AcikVadeParcasi(sinif="customer", vade_gun=46, tutar=1_000_000.0,
                            kod="120.1", unvan="X"),
            AcikVadeParcasi(sinif="supplier", vade_gun=30, tutar=500_000.0,
                            kod="320.1", unvan="Y"),
        ]
        w = build_reel_deger_widget(
            build_reel_deger_analizi(ta, ReelDegerVarsayim()),
            bas="2026-01-01", bit="2026-07-31")
        try:
            kpi_basliklar = [
                lb.text() for lb in w.findChildren(QLabel)
                if lb.text().startswith(("NOMİNAL", "VADE", "NET VADE", "ALACAĞIN", "BORCUN"))]
            self.assertFalse(
                [b for b in kpi_basliklar if b.startswith(("NOMİNAL", "ALACAĞIN", "BORCUN"))],
                f"hero panellerin tekrarı: {kpi_basliklar}")
            self.assertTrue(any(b.startswith("VADE MALİYETİ") for b in kpi_basliklar))
        finally:
            w.deleteLater()


if __name__ == "__main__":
    unittest.main()
