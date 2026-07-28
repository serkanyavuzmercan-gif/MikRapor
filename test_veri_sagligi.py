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
    Canlıda 2 adet mala 3,3 trilyon TL yazan tek kayıt vardı (07.12.2023, yevmiye 731).

    O yılı içeren her rapor bundan zehirleniyordu ve bulmak için elle teşhis gerekti.
    """

    _BOZUK = {"sth_tip": 0, "sth_evraktip": 12, "tutar": 3_333_333_333_340.0, "adet": 2}
    _NORMAL = {"sth_tip": 1, "sth_evraktip": 1, "tutar": 19_386_234.0, "adet": 17_914}

    def test_aykiri_satir_yakalanir(self) -> None:
        vs = build_veri_sagligi(stok_rows=[self._NORMAL, self._BOZUK])
        self.assertIn("bozuk_stok", _kodlar(vs))
        b = next(x for x in vs.bulgular if x.kod == "bozuk_stok")
        self.assertEqual(b.onem, KRITIK)
        self.assertIn("0 12", b.ne_yapmali)      # hangi türe bakılacağı yazıyor

    def test_normal_hareket_bulgu_uretmez(self) -> None:
        vs = build_veri_sagligi(stok_rows=[self._NORMAL])
        self.assertNotIn("bozuk_stok", _kodlar(vs))

    def test_sifir_adet_bolme_hatasi_vermez(self) -> None:
        vs = build_veri_sagligi(stok_rows=[{"sth_tip": 1, "sth_evraktip": 1,
                                            "tutar": 5.0, "adet": 0}])
        self.assertNotIn("bozuk_stok", _kodlar(vs))


class TestTanimsizEvrak(unittest.TestCase):
    """Canlıda tip=1/evraktip=0 · 187 satır · 200.964 TL — ne olduğu hâlâ bilinmiyor."""

    def test_bilinmeyen_tur_uyari_verir(self) -> None:
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "tutar": 19_386_234.0, "adet": 17_914},
            {"sth_tip": 1, "sth_evraktip": 0, "tutar": 200_964.0, "adet": 187},
        ])
        b = next(x for x in vs.bulgular if x.kod == "tanimsiz_evrak")
        self.assertEqual(b.onem, UYARI)
        self.assertIn("evraktip=0", b.ne_yapmali)

    def test_bilinen_turler_sessiz(self) -> None:
        vs = build_veri_sagligi(stok_rows=[
            {"sth_tip": 0, "sth_evraktip": 3, "tutar": 100.0, "adet": 1},
            {"sth_tip": 1, "sth_evraktip": 16, "tutar": 20.0, "adet": 1},
        ])
        self.assertNotIn("tanimsiz_evrak", _kodlar(vs))


class TestMaliyetsizSatis(unittest.TestCase):
    """Canlıda satış satırlarının %11'i maliyetsizdi — her ay aynı, sistematik."""

    def test_dusuk_doluluk_uyari_verir(self) -> None:
        vs = build_veri_sagligi(maliyet_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "adet": 17_914, "ana_dolu": 16_100},
            {"sth_tip": 1, "sth_evraktip": 4, "adet": 262, "ana_dolu": 147},
        ])
        b = next(x for x in vs.bulgular if x.kod == "maliyetsiz_satis")
        self.assertEqual(b.onem, UYARI)
        self.assertIn("%11", b.olcum)

    def test_sarf_fisi_orana_katilmaz(self) -> None:
        """Sarf fişinin maliyeti olmaması normal; onu saymak kolonu haksız yere yakar."""
        vs = build_veri_sagligi(maliyet_rows=[
            {"sth_tip": 1, "sth_evraktip": 1, "adet": 1000, "ana_dolu": 1000},
            {"sth_tip": 1, "sth_evraktip": 16, "adet": 1000, "ana_dolu": 0},
        ])
        self.assertNotIn("maliyetsiz_satis", _kodlar(vs))


class TestOkunamayanKaynak(unittest.TestCase):
    """
    Kontrol EDİLEMEYEN alan, temiz çıkan alandan farklıdır.

    İkisini aynı göstermek kullanıcıya olmayan bir güven verir — bu, hatanın
    kendisinden daha kötüdür.
    """

    def test_verilmeyen_kaynak_icin_bulgu_uydurulmaz(self) -> None:
        vs = build_veri_sagligi(bilanco=None, stok_rows=None, maliyet_rows=None)
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
