"""
Veri Sağlığı — bu oturumda ELLE bulunan bozuklukları program kendi bulabilmeli.

Buradaki her senaryo canlıda gerçekten yaşandı. Testin amacı, aynı bozukluk bir daha
çıktığında kullanıcının bana sormak zorunda kalmaması.
"""

from __future__ import annotations

import unittest

from domain.mizan_bilanco import build_bilanco
from domain.veri_sagligi import KRITIK, UYARI, build_veri_sagligi, veri_sagligi_csv


def _bilanco(*, smm: float = 0.0, dengeli: bool = True):
    """
    DENGELİ bir mizan üretir: aktif = pasif + dönem kârı.

    Ciro maliyete göre ölçekleniyor (brüt sabit 200.000) — böylece `smm` değişse de
    denge bozulmuyor ve maliyet kontrolü tek başına sınanabiliyor. Denge kontrolünü
    sınamak için `dengeli=False` verilir.
    """
    satirlar = [
        {"hesap_kodu": "102", "borc": 100_000.0, "alacak": 0.0},
        {"hesap_kodu": "153", "borc": 800_000.0, "alacak": 0.0},   # aktif 900.000
        {"hesap_kodu": "320", "borc": 0.0, "alacak": 300_000.0},
        {"hesap_kodu": "500", "borc": 0.0, "alacak": 400_000.0},   # + dönem kârı 200.000
        {"hesap_kodu": "600", "borc": 0.0, "alacak": smm + 200_000.0},
    ]
    if smm:
        satirlar.append({"hesap_kodu": "621", "borc": smm, "alacak": 0.0})
    if not dengeli:
        satirlar.append({"hesap_kodu": "102", "borc": 500_000.0, "alacak": 0.0})
    return build_bilanco(satirlar, asof="2026-07-28")


def _kodlar(vs) -> set[str]:
    return {b.kod for b in vs.bulgular}


class TestMaliyetKapanisi(unittest.TestCase):
    """62 işlenmemişse kâr DA stok DA şişik — kullanıcının en çok yandığı sorun."""

    def test_smm_yoksa_kritik_bulgu(self) -> None:
        vs = build_veri_sagligi(bilanco=_bilanco(smm=0.0))
        self.assertIn("maliyet_kapanisi", _kodlar(vs))
        b = next(x for x in vs.bulgular if x.kod == "maliyet_kapanisi")
        self.assertEqual(b.onem, KRITIK)
        self.assertIn("müşavir", b.ne_yapmali.lower())   # ne yapacağı yazıyor

    def test_smm_islenmisse_bulgu_yok(self) -> None:
        vs = build_veri_sagligi(bilanco=_bilanco(smm=700_000.0))
        self.assertNotIn("maliyet_kapanisi", _kodlar(vs))


class TestBozukStokKaydi(unittest.TestCase):
    """
    Canlıda 13 aykırı satır vardı; biri 2 adet mala 3,3 TRİLYON TL yazıyordu
    (07.12.2023, yevmiye 731). O yılı içeren her rapor bundan zehirleniyordu.

    EŞİK BURADA DEĞİL, SORGUDA ÖLÇÜLÜR (infra.mikro_fetch.AYKIRI_KAT): satır, dönemin
    ortalama satırının on binlerce katıysa aykırıdır. Eskiden mutlak bir sınır vardı
    («satır başına 2 milyon TL»); bu program Mikro kullanan HER firmaya satılacak ve
    mutlak sınır küçük firmada hiçbir şey yakalamaz, büyükte gerçek faturayı bozuk ilan
    ederdi. Sorgu aykırıyı toplamdan çıkarıp ayrı sütunda döndürür.
    """

    _NORMAL = {"sth_tip": 1, "sth_evraktip": 1, "tutar": 19_386_234.0, "adet": 17_914,
               "aykiri_adet": 0, "aykiri_tutar": 0.0}
    _AYKIRILI = {"sth_tip": 0, "sth_evraktip": 12, "tutar": 22_594_651.34, "adet": 6_592,
                 "aykiri_adet": 1, "aykiri_tutar": 3_333_333_333_340.0}

    def test_elenen_satir_bulgu_uretir(self) -> None:
        vs = build_veri_sagligi(stok_rows=[self._NORMAL, self._AYKIRILI])
        b = next(x for x in vs.bulgular if x.kod == "bozuk_stok")
        self.assertEqual(b.onem, KRITIK)
        self.assertIn("1 satır", b.olcum)
        # CLI komutu YOK: satılan üründe kullanıcıya terminal komutu verilmez.
        self.assertNotIn("stok_diag_cli", b.ne_yapmali)
        self.assertIn("Mikro", b.ne_yapmali)

    def test_elenen_tutar_rakamin_yaninda_yazar(self) -> None:
        """Sessizce atılan rakam, yanlış rakamdan iyi değildir."""
        vs = build_veri_sagligi(stok_rows=[self._AYKIRILI])
        b = next(x for x in vs.bulgular if x.kod == "bozuk_stok")
        self.assertIn("3.333.333.333.340,00", b.olcum)
        self.assertIn("ALINMADI", b.etkisi)

    def test_normal_hareket_bulgu_uretmez(self) -> None:
        vs = build_veri_sagligi(stok_rows=[self._NORMAL])
        self.assertNotIn("bozuk_stok", _kodlar(vs))

    def test_aykiri_sutunu_olmayan_satir_cokmez(self) -> None:
        """Eski/kısmi sorgu çıktısı gelirse bulgu uydurulmaz."""
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "tutar": 5.0, "adet": 0}])
        self.assertNotIn("bozuk_stok", _kodlar(vs))


class TestBozukKayitListesi(unittest.TestCase):
    """
    «13 bozuk kayıt var, düzeltin» demek yetmez.

    Kullanıcı 390 bin satır içinde o 13'ünü bulamaz. Bulgu, Mikro'da evrakı açmaya
    yetecek kadar bilgi taşımalı: tarih, evrak no, stok kodu, miktar, tutar.
    """

    _STOK = [{"sth_tip": 0, "sth_evraktip": 12, "tutar": 22_594_651.34, "adet": 6_592,
              "aykiri_adet": 2, "aykiri_tutar": 3_333_333_333_340.0}]
    _AYKIRI = [
        {"tarih": "2023-12-07T00:00:00", "sth_evrakno_seri": "A",
         "sth_evrakno_sira": 731, "sth_stok_kod": "MAL.001", "sth_tip": 0,
         "sth_evraktip": 12, "sth_miktar": 2.0, "sth_tutar": 3_333_333_333_340.0},
        {"tarih": "2024-05-02T00:00:00", "sth_evrakno_seri": "",
         "sth_evrakno_sira": 0, "sth_belge_no": "IRS-9", "sth_stok_kod": "MAL.002",
         "sth_tip": 0, "sth_evraktip": 12, "sth_miktar": 1.0, "sth_tutar": 9_000_000.0},
    ]

    def _bulgu(self, **kw):
        vs = build_veri_sagligi(stok_rows=self._STOK, **kw)
        return next(b for b in vs.bulgular if b.kod == "bozuk_stok")

    def test_kayit_satiri_evraki_bulmaya_yeter(self) -> None:
        b = self._bulgu(aykiri_rows=self._AYKIRI)
        self.assertEqual(len(b.kayitlar), 2)
        ilk = b.kayitlar[0]
        for parca in ("2023-12-07", "A731", "MAL.001", "3.333.333.333.340,00"):
            self.assertIn(parca, ilk)

    def test_evrak_serisi_yoksa_belge_no_kullanilir(self) -> None:
        b = self._bulgu(aykiri_rows=self._AYKIRI)
        self.assertIn("IRS-9", b.kayitlar[1])

    def test_liste_cekilemezse_bulgu_yine_gosterilir(self) -> None:
        """Kayıt listesi düşse de «2 satır, 3,3 trilyon» bilgisi kaybolmamalı."""
        b = self._bulgu()
        self.assertEqual(b.kayitlar, [])
        self.assertIn("2 satır", b.olcum)

    def test_kayitlar_csvye_de_girer(self) -> None:
        vs = build_veri_sagligi(stok_rows=self._STOK, aykiri_rows=self._AYKIRI)
        csv = veri_sagligi_csv(vs)
        self.assertIn("BULGU;KAYIT", csv)
        self.assertIn("MAL.001", csv)


class TestTanimsizEvrak(unittest.TestCase):
    """
    Tanımsız evrak tipi yalnız ÖNEMLİ tutarda gösterilir.

    Canlıda tip=1/evraktip=0 cironun %1'iydi ve ekranda «bize bildirin» diyordu:
    kullanıcının yapabileceği bir şey yok, üstelik satılan bir üründe «biz» diye bir
    muhatap da yok. Küçük tutar artık hiç gösterilmiyor.
    """

    def test_kucuk_tutar_gosterilmez(self) -> None:
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "tutar": 19_386_234.0, "adet": 17_914},
            {"sth_tip": 1, "sth_evraktip": 0, "tutar": 200_964.0, "adet": 187},
        ])
        self.assertNotIn("tanimsiz_evrak", _kodlar(vs))

    def test_buyuk_tutar_gosterilir(self) -> None:
        """Cironun beşte biri sınıflanamıyorsa rakamlar gerçekten eksik demektir."""
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "tutar": 10_000_000.0, "adet": 5_000},
            {"sth_tip": 1, "sth_evraktip": 0, "tutar": 4_000_000.0, "adet": 900},
        ])
        b = next(x for x in vs.bulgular if x.kod == "tanimsiz_evrak")
        self.assertEqual(b.onem, UYARI)
        self.assertNotIn("bildirin", b.ne_yapmali)     # muhatap yok
        self.assertIn("%29", b.olcum)                  # ne kadar eksik olduğu

    def test_bilinen_turler_sessiz(self) -> None:
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 0, "sth_evraktip": 3, "tutar": 100.0, "adet": 1},
            {"sth_tip": 1, "sth_evraktip": 16, "tutar": 20.0, "adet": 1},
        ])
        self.assertNotIn("tanimsiz_evrak", _kodlar(vs))


class TestOkunamayanKaynak(unittest.TestCase):
    """
    Kontrol EDİLEMEYEN alan, temiz çıkan alandan farklıdır.

    İkisini aynı göstermek kullanıcıya olmayan bir güven verir — bu, hatanın
    kendisinden daha kötüdür.
    """

    def test_verilmeyen_kaynak_icin_bulgu_uydurulmaz(self) -> None:
        vs = build_veri_sagligi(bilanco=None, stok_rows=None)
        self.assertTrue(vs.temiz)

    def test_okunamayan_listesi_ozette_kalir(self) -> None:
        vs = build_veri_sagligi(okunamayan=["Muhasebe mizanı"])
        self.assertEqual(vs.okunamayan, ["Muhasebe mizanı"])
        self.assertIn("Muhasebe mizanı", veri_sagligi_csv(vs))


class TestOzet(unittest.TestCase):
    def test_temiz_veri(self) -> None:
        vs = build_veri_sagligi(bilanco=_bilanco(smm=700_000.0), stok_rows=[])
        self.assertTrue(vs.temiz)
        self.assertIn("sağlıklı", vs.ozet())

    def test_kritik_once_siralanir(self) -> None:
        """Kullanıcı listenin başından okur; kritik olan aşağıda kalmamalı."""
        vs = build_veri_sagligi(
            bilanco=_bilanco(smm=0.0),
            stok_rows=[{"sth_tip": 1, "sth_evraktip": 0, "tutar": 200.0, "adet": 187}])
        self.assertEqual(vs.bulgular[0].onem, KRITIK)
        self.assertIn("kritik", vs.ozet())


if __name__ == "__main__":
    unittest.main()
