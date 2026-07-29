"""Nakit Akış motoru testleri — kategorize giriş/çıkış, kredi, açılış/kapanış, aylık trend."""

import unittest

from domain.nakit_akis import _kategori, build_nakit_akis, hesap_kirilim_etiketi, nakit_akis_csv


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
        self.assertAlmostEqual(self.na.giris_kategori["Banka kredisi kullanımı"], 40000, places=2)
        self.assertAlmostEqual(self.na.giris_kategori["Diğer girişler"], 5000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Satıcı ödemesi"], 60000, places=2)
        self.assertAlmostEqual(self.na.cikis_kategori["Banka kredisi ödemeleri"], 25000, places=2)
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

    def test_kredi_karti_banka_kredisinden_ayrilir(self):
        rows = [
            _h("2026-01", 1, "300", 25000),
            _h("2026-01", 1, "KKT", 70000),
        ]
        na = build_nakit_akis(
            rows, kapanis_nakit=-95000, donem_delta=-95000,
            bas="2026-01-01", bit="2026-01-31",
        )
        self.assertAlmostEqual(na.cikis_kategori["Banka kredisi ödemeleri"], 25000, places=2)
        self.assertAlmostEqual(na.cikis_kategori["Kredi kartı ödemeleri"], 70000, places=2)
        self.assertAlmostEqual(na.kredi_odeme, 25000, places=2)

    def test_diger_kirilim(self):
        rows = [_h("2026-01", 0, "600.01", 30000), _h("2026-01", 0, "127.01", 20000)]
        na = build_nakit_akis(rows, kapanis_nakit=50000, donem_delta=50000,
                              bas="2026-01-01", bit="2026-02-28")
        kirilim = dict(na.diger_giris_kirilim)
        self.assertAlmostEqual(kirilim["600.01"], 30000, places=2)
        self.assertAlmostEqual(kirilim["127.01"], 20000, places=2)

    def test_genel_giderler_hesap_kirilimi(self):
        rows = [_h("2026-01", 1, "770.01", 30000), _h("2026-01", 1, "760.02", 20000)]
        na = build_nakit_akis(rows, kapanis_nakit=-50000, donem_delta=-50000,
                              bas="2026-01-01", bit="2026-01-31")
        self.assertAlmostEqual(na.cikis_kategori["Genel giderler"], 50000, places=2)
        kirilim = dict(na.gider_cikis_kirilim)
        self.assertAlmostEqual(kirilim["770.01"], 30000, places=2)
        self.assertAlmostEqual(kirilim["760.02"], 20000, places=2)

    def test_hesap_kirilim_etiketi_tdph_adini_icerir(self):
        self.assertEqual(hesap_kirilim_etiketi("780"), "780 — Finansman Giderleri")
        self.assertEqual(hesap_kirilim_etiketi("770.01"), "770.01 — Genel Yönetim Giderleri")

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
        self.assertEqual(_kategori("KKT"), "kredi_karti")
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
        self.assertIn("Anapara Kapama / Borç Azalışı", csv)
        self.assertIn("Net Nakit Akışı", csv)

    def test_bos_veri(self):
        na = build_nakit_akis([], bas="2026-01-01", bit="2026-02-28")
        self.assertEqual(na.hareket_sayisi, 0)
        self.assertAlmostEqual(na.net_akis, 0, places=2)


class TestKrediGLYedek(unittest.TestCase):
    """Kredi banka hareketlerine işlenmemişse muhasebe (GL) tutarı gösterilmeli."""

    def test_gl_yedegi_devreye_girer(self):
        na = build_nakit_akis([], bas="2026-01-01", bit="2026-06-30")
        self.assertAlmostEqual(na.kredi_odeme, 0.0, places=2)
        na.kredi_odeme_gl = 1_435_866.96
        na.kredi_kullanim_gl = 200_000.0
        self.assertTrue(na.kredi_kaynak_gl)
        self.assertAlmostEqual(na.kredi_odeme_gosterim, 1_435_866.96, places=2)
        self.assertAlmostEqual(na.kredi_kullanim_gosterim, 200_000.0, places=2)
        self.assertAlmostEqual(na.kredi_net_gosterim, 200_000.0 - 1_435_866.96, places=2)

    def test_banka_hareketi_varsa_gl_kullanilmaz(self):
        na = build_nakit_akis(
            [_h("2026-01", 1, "300.01", 25000)], bas="2026-01-01", bit="2026-06-30")
        na.kredi_odeme_gl = 999_999.0  # GL farklı olsa bile banka hareketi öncelikli
        self.assertFalse(na.kredi_kaynak_gl)
        self.assertAlmostEqual(na.kredi_odeme_gosterim, 25000.0, places=2)

    def test_kredi_ozeti_gl_borc_hareketini_onceler(self):
        na = build_nakit_akis(
            [_h("2026-01", 1, "300.01", 25000)], bas="2026-01-01", bit="2026-06-30")
        na.kredi_odeme_gl = 80000.0
        na.kredi_kullanim_gl = 120000.0
        na.kredi_ozet_gl = True
        self.assertTrue(na.kredi_kaynak_gl)
        self.assertAlmostEqual(na.kredi_odeme_gosterim, 80000.0, places=2)
        self.assertAlmostEqual(na.kredi_net_gosterim, 40000.0, places=2)

    def test_csv_kaynak_satiri(self):
        na = build_nakit_akis([], bas="2026-01-01", bit="2026-06-30")
        na.kredi_odeme_gl = 500_000.0
        csv = nakit_akis_csv(na)
        self.assertIn("muhasebe kayıtları (300/303)", csv)

    def test_gl_kaynakli_akis(self):
        """GL (yevmiye) satırları: çek ödemesi (103) satıcıya, 131 ortağa, mutabakat kapanır."""
        rows = [
            _h("2026-01", 0, "120", 1_000_000),   # tahsilat
            _h("2026-01", 0, "300", 400_000),     # kredi kullanımı (GL karşı hesap)
            _h("2026-01", 1, "103", 700_000),     # çekle satıcı ödemesi → satici
            _h("2026-01", 1, "131", 50_000),      # ortaklardan alacaklar → ortak
            _h("2026-01", 1, "780", 30_000),      # finansman gideri → gider
        ]
        net = 1_400_000 - 780_000
        na = build_nakit_akis(rows, kapanis_nakit=net, donem_delta=net,
                              bas="2026-01-01", bit="2026-01-31")
        na.kaynak = "gl"
        self.assertAlmostEqual(na.cikis_kategori.get("Satıcı ödemesi", 0), 700_000, places=2)
        self.assertAlmostEqual(na.cikis_kategori.get("Ortaklar", 0), 50_000, places=2)
        self.assertAlmostEqual(na.kredi_kullanim, 400_000, places=2)
        self.assertAlmostEqual(na.acilis_nakit, 0.0, places=2)     # kapanış − delta
        self.assertAlmostEqual(na.mutabakat_farki, 0.0, places=2)  # aynı kaynak → kapanır


class TestBaslangicNakitKaynagi(unittest.TestCase):
    """
    Sessiz 0 yasak: başlangıç nakdi ölçülemediğinde SEBEBİ söylenmeli (kural 2).

    Eskiden yalnız MikroAPIError yakalanıyordu. GL okunup 0 dönerse (kurulumda nakit
    başka hesap kodlarında tutuluyorsa olur — kural 6) o 0 sessizce başlangıç nakdi
    oluyor, cari yedeğe hiç düşülmüyordu. Projeksiyonun tamamı bu rakama dayanıyor.
    """

    def test_gl_okunduysa_gl_kullanilir(self):
        from domain.nakit_akis import baslangic_nakit_sec
        self.assertEqual(baslangic_nakit_sec(1_500_000.0, 9_999.0), (1_500_000.0, "gl"))

    def test_gl_negatif_de_gecerli_bir_olcumdur(self):
        """Eksi banka bakiyesi gerçek bir ölçümdür; 0 sanıp cari'ye düşmek yanlış olur."""
        from domain.nakit_akis import baslangic_nakit_sec
        self.assertEqual(baslangic_nakit_sec(-250_000.0, 800_000.0), (-250_000.0, "gl"))

    def test_gl_okunamazsa_cariye_dusulur(self):
        from domain.nakit_akis import baslangic_nakit_sec
        self.assertEqual(baslangic_nakit_sec(None, 640_000.0), (640_000.0, "cari"))

    def test_gl_sifir_okunursa_da_cariye_dusulur(self):
        """Asıl açık buydu: 0 bir hata değil «bulunamadı» olabilir, sessizce kullanılmaz."""
        from domain.nakit_akis import baslangic_nakit_sec
        self.assertEqual(baslangic_nakit_sec(0.0, 640_000.0), (640_000.0, "cari"))

    def test_ikisi_de_bossa_sifir_ama_kaynak_yok_der(self):
        from domain.nakit_akis import baslangic_nakit_sec
        self.assertEqual(baslangic_nakit_sec(0.0, 0.0), (0.0, "yok"))

    def test_her_kaynak_icin_not_var_gl_icin_sessiz(self):
        """gl beklenen hâl → uyarı yok. Diğer ikisi sebebini yazmak ZORUNDA."""
        from domain.nakit_akis import NAKIT_KAYNAK_NOTU
        self.assertEqual(NAKIT_KAYNAK_NOTU["gl"], "")
        for kaynak in ("cari", "yok"):
            self.assertTrue(NAKIT_KAYNAK_NOTU[kaynak].strip(),
                            f"{kaynak} için sebep metni yok — kural 2 ihlali")

    def test_notlar_terminal_komutu_ya_da_bize_bildirin_demez(self):
        """Kural 3b: tavsiye Mikro'da yapılabilecek bir şey olmalı."""
        from domain.nakit_akis import NAKIT_KAYNAK_NOTU
        for metin in NAKIT_KAYNAK_NOTU.values():
            d = metin.lower()
            self.assertNotIn("bize bildir", d)
            self.assertNotIn(".py", d)


if __name__ == "__main__":
    unittest.main()


class TestDetayOzetleAyniKaynak(unittest.TestCase):
    """
    Kanıt penceresinin TEK işi var: paneldeki rakamı doğrulamak.

    Detay ayrı bir sorgu olarak yazılsaydı er ya da geç toplamdan ayrışırdı — «özet
    3M diyor, döküm 2,8M» durumu hiç detay olmamasından kötüdür. Bu yüzden iki sorgu
    aynı SQL gövdesini paylaşıyor ve sınıflama aynı fonksiyonla yapılıyor.
    """

    def _sql(self, cek) -> str:
        class Sahte:
            class cfg:
                firma_kodu = "26"

            def sql_veri_oku(self, sql, **_kw):
                self.son = sql
                return []

        s = Sahte()
        cek(s)
        return s.son

    def test_ayni_alt_sorgu(self) -> None:
        from infra.mikro_fetch import fetch_nakit_akis_detay, fetch_nakit_akis_gl
        ozet = self._sql(lambda c: fetch_nakit_akis_gl(c, "2026-01-01", "2026-07-29"))
        detay = self._sql(
            lambda c: fetch_nakit_akis_detay(c, "2026-01-01", "2026-07-29", 0))
        govde = ozet[ozet.index("FROM ("):].split(" GROUP BY")[0]
        self.assertIn(govde, detay)

    def test_siniflama_ayni_fonksiyondan(self) -> None:
        """Detay penceresi kategoriyi kendi eşlemesiyle değil, özetinkiyle bulur."""
        from domain.nakit_akis import GIRIS_ETIKET, kategori_etiketi
        self.assertEqual(kategori_etiketi("120", 0), GIRIS_ETIKET["musteri"])
        self.assertEqual(kategori_etiketi("320", 1), "Satıcı ödemesi")
        self.assertEqual(kategori_etiketi("KKT", 1), "Kredi kartı ödemeleri")
        # Tanınmayan önek iki tarafta da «diğer» kovasına düşer.
        self.assertEqual(kategori_etiketi("999", 0), GIRIS_ETIKET["diger"])

    def test_detay_toplami_kategori_toplamini_verir(self) -> None:
        """Aynı ham satırlardan özet ve döküm aynı rakamı üretmeli."""
        from domain.nakit_akis import build_nakit_akis, kategori_etiketi
        ham = [{"ay": "2026-01", "tip": 0, "prefix": "120", "tutar": 5000.0},
               {"ay": "2026-02", "tip": 0, "prefix": "121", "tutar": 7000.0},
               {"ay": "2026-03", "tip": 0, "prefix": "320", "tutar": 900.0}]
        na = build_nakit_akis(ham, kapanis_nakit=0.0, bas="2026-01-01", bit="2026-07-29")
        etiket = kategori_etiketi("120", 0)
        panel = na.giris_kategori[etiket]
        dokum = sum(r["tutar"] for r in ham
                    if kategori_etiketi(r["prefix"], r["tip"]) == etiket)
        self.assertAlmostEqual(panel, dokum)
        self.assertAlmostEqual(panel, 12000.0)


class TestKrediHesabiTekKural(unittest.TestCase):
    """
    «Bu banka hesabı kredi mi» TEK kuraldır: ban_hesap_tip=1 · 300 öneki · 320 sınıfı.

    Niyet gercek_durum_ayarlar.py'de yazılıydı («300.* ve ban_hesap_tip=1 nakitten
    hariç») ama üç yerde üç farklı tamlıkta uygulanmıştı. Canlı kurulumda kredi
    hesaplarının ban_hesap_tip'i 1 DEĞİL (300.02.* mevduat gibi görünüyor), o yüzden
    tek teste güvenen iki uygulama krediyi nakit sayıyordu.
    """

    def test_ban_hesap_tip_bos_olsa_bile_300_kredi_sayilir(self):
        from domain.ortak import kredi_banka_mi
        self.assertTrue(kredi_banka_mi({"kod": "300.02.0001", "ban_hesap_tip": 0}))
        self.assertTrue(kredi_banka_mi({"ban_muh_kod": "300.02", "ban_hesap_tip": 0}))
        self.assertTrue(kredi_banka_mi({"ban_hesap_tip": 1}))

    def test_mevduat_hesabi_kredi_sayilmaz(self):
        from domain.ortak import kredi_banka_mi
        self.assertFalse(kredi_banka_mi({"kod": "102.01.0004", "ban_hesap_tip": 0}))

    def test_nakit_bakiye_kredi_hesabini_nakde_katmaz(self):
        """
        Canlıda 7 kredi hesabının net -3.744.328'i nakde katılıyordu. Tahmin krediyi
        ayrıca taksit taksit modellediği için borç İKİ KEZ sayılıyordu.
        """
        from domain.nakit_akis import nakit_bakiye
        satirlar = [
            {"cins": 2, "kod": "102.01.0004", "ban_hesap_tip": 0,
             "borc_h": 9_456_672.88, "alacak_h": 3_033_866.53},
            {"cins": 2, "kod": "300.02.0001", "ban_hesap_tip": 0,   # KREDİ, tip 1 DEĞİL
             "borc_h": 2_136_342.44, "alacak_h": 1_316_696.17},
            {"cins": 4, "kod": "KASA01", "borc_h": 523_705.79, "alacak_h": 0.0},
        ]
        beklenen = (9_456_672.88 - 3_033_866.53) + 523_705.79
        self.assertAlmostEqual(nakit_bakiye(satirlar), beklenen, places=2)

    def test_iki_domain_okuyucusu_ayni_sonucu_verir(self):
        """nakit_bakiye ile _bakiye_caridan aynı satırlarda aynı nakdi bulmalı."""
        from domain.gercek_durum import _bakiye_caridan
        from domain.nakit_akis import nakit_bakiye
        satirlar = [
            {"cins": 2, "kod": "102.01.0004", "ban_hesap_tip": 0,
             "borc_h": 1_000_000.0, "alacak_h": 250_000.0},
            {"cins": 2, "kod": "300.02.0001", "ban_hesap_tip": 0,
             "borc_h": 800_000.0, "alacak_h": 900_000.0},
            {"cins": 4, "kod": "KASA01", "borc_h": 50_000.0, "alacak_h": 0.0},
        ]
        self.assertAlmostEqual(
            nakit_bakiye(satirlar), _bakiye_caridan(satirlar)["nakit_mevcut"], places=2)
