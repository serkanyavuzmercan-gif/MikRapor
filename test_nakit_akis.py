"""Nakit Akış motoru testleri — kategorize giriş/çıkış, kredi, açılış/kapanış, aylık trend."""

import unittest

from domain.nakit_akis import _kategori, build_nakit_akis, nakit_akis_csv


def _h(ay, tip, prefix, tutar):
    return {"ay": ay, "tip": tip, "prefix": prefix, "tutar": tutar}


def _bakiye(cins, borc_h, alacak_h, ban_hesap_tip=-1):
    return {"cins": cins, "borc_h": borc_h, "alacak_h": alacak_h, "ban_hesap_tip": ban_hesap_tip}


def _hareketler():
    return [
        # Girişler (tip 0)
        _h("2026-01", 0, "120.01", 100000),   # müşteri tahsilatı
        _h("2026-02", 0, "120.02", 50000),    # müşteri tahsilatı
        _h("2026-01", 0, "300.01", 40000),    # kredi kullanımı
        _h("2026-02", 0, "190.00", 5000),     # diğer giriş
        # Çıkışlar (tip 1)
        _h("2026-01", 1, "320.01", 60000),    # satıcı ödemesi
        _h("2026-02", 1, "300.01", 25000),    # kredi ödemesi
        _h("2026-01", 1, "360.01", 15000),    # vergi
        _h("2026-02", 1, "335.01", 8000),     # ortak/personel
    ]


class TestNakitAkis(unittest.TestCase):
    def setUp(self):
        # Kapanış 287k; dönem deltası = net (87k) → açılış = 287 − 87 = 200k
        kapanis = [_bakiye(2, 240000, 13000), _bakiye(4, 60000, 0)]  # 227k+60k=287k
        self.na = build_nakit_akis(
            _hareketler(), bakiye_kapanis_rows=kapanis, donem_delta=87000,
            bas="2026-01-01", bit="2026-02-28")

    def test_toplamlar(self):
        self.assertAlmostEqual(self.na.toplam_giris, 195000, places=2)  # 100+50+40+5
        self.assertAlmostEqual(self.na.toplam_cikis, 108000, places=2)  # 60+25+15+8
        self.assertAlmostEqual(self.na.net_akis, 87000, places=2)

    def test_kategoriler(self):
        self.assertAlmostEqual(self.na.giris_kategori["Müşteri tahsilatı"], 150000, places=2)
        self.assertAlmostEqual(self.na.giris_kategori["Kredi kullanımı"], 40000, places=2)
        self.assertAlmostEqual(self.na.giris_kategori["Diğer girişler"], 5000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Satıcı ödemesi"], 60000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Kredi ödemesi"], 25000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Vergi"], 15000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Personel / Maaş"], 8000, places=2)

    def test_kredi(self):
        self.assertAlmostEqual(self.na.kredi_kullanim, 40000, places=2)
        self.assertAlmostEqual(self.na.kredi_odeme, 25000, places=2)
        self.assertAlmostEqual(self.na.kredi_net, 15000, places=2)

    def test_acilis_kapanis(self):
        self.assertAlmostEqual(self.na.acilis_nakit, 200000, places=2)
        self.assertAlmostEqual(self.na.kapanis_nakit, 287000, places=2)
        self.assertAlmostEqual(self.na.kapanis_hesaplanan, 287000, places=2)  # 200k + 87k net
        self.assertAlmostEqual(self.na.mutabakat_farki, 0, places=2)

    def test_kredi_bankasi_haric(self):
        # ban_hesap_tip=1 (kredi hesabı) nakit sayılmaz
        rows = [_bakiye(2, 100000, 0), _bakiye(2, 500000, 0, ban_hesap_tip=1)]
        na = build_nakit_akis([], bakiye_kapanis_rows=rows, bas="2026-01-01", bit="2026-02-28")
        self.assertAlmostEqual(na.kapanis_nakit, 100000, places=2)

    def test_kredi_sentinel_ve_mutabakat(self):
        # 'KRD' öneki (kredi hesabına/hesabından) → kredi kategorisi
        rows = [_h("2026-01", 1, "KRD", 70000), _h("2026-01", 0, "120.01", 50000)]
        na = build_nakit_akis(rows, kapanis_nakit=480000, donem_delta=-20000,
                              bas="2026-01-01", bit="2026-02-28")
        self.assertAlmostEqual(na.kredi_odeme, 70000, places=2)
        self.assertAlmostEqual(na.kredi_net, -70000, places=2)
        self.assertAlmostEqual(na.acilis_nakit, 500000, places=2)   # 480k − (−20k)
        self.assertAlmostEqual(na.mutabakat_farki, 0, places=2)      # delta(−20k) = net(50−70)

    def test_diger_kirilim(self):
        rows = [_h("2026-01", 0, "600.01", 30000), _h("2026-01", 0, "127.01", 20000)]
        na = build_nakit_akis(rows, kapanis_nakit=50000, donem_delta=50000,
                              bas="2026-01-01", bit="2026-02-28")
        kirilim = dict(na.diger_giris_kirilim)
        self.assertAlmostEqual(kirilim["600.01"], 30000, places=2)
        self.assertAlmostEqual(kirilim["127.01"], 20000, places=2)

    def test_aylik_trend(self):
        aylar = {a.ay: a for a in self.na.aylik}
        self.assertAlmostEqual(aylar["2026-01"].giris, 140000, places=2)  # 100k + 40k
        self.assertAlmostEqual(aylar["2026-01"].cikis, 75000, places=2)   # 60k + 15k
        self.assertAlmostEqual(aylar["2026-02"].net, 55000 - 33000, places=2)  # giriş 55k - çıkış 33k

    def test_kategori_eslemesi(self):
        self.assertEqual(_kategori("120.01.0001"), "musteri")
        self.assertEqual(_kategori("320.05"), "satici")
        self.assertEqual(_kategori("300.01"), "kredi")
        self.assertEqual(_kategori("KRD"), "kredi")
        self.assertEqual(_kategori("360.10"), "vergi")
        self.assertEqual(_kategori("361.01"), "sgk")
        self.assertEqual(_kategori("335.01"), "personel")
        self.assertEqual(_kategori("331.01"), "ortak")
        self.assertEqual(_kategori("770.01"), "gider")
        self.assertEqual(_kategori("999.01"), "diger")
        self.assertEqual(_kategori(""), "diger")

    def test_csv(self):
        csv = nakit_akis_csv(self.na)
        self.assertIn("GİRİŞLER", csv)
        self.assertIn("Kredi Ödemesi", csv)
        self.assertIn("Net Nakit Akışı", csv)

    def test_bos_veri(self):
        na = build_nakit_akis([], bas="2026-01-01", bit="2026-02-28")
        self.assertEqual(na.hareket_sayisi, 0)
        self.assertAlmostEqual(na.net_akis, 0, places=2)


if __name__ == "__main__":
    unittest.main()
