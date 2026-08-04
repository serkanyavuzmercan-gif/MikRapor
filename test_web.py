"""
Tanıtım sayfası bekçisi — site ile uygulama aynı şeyi söylesin.

NEDEN VAR: sayfa aylarca «Trend & oranlar» diye bir sekmeden bahsetti; uygulamada o
sekmenin adı «Mukayese & Oranlar»dı. Kural 5 («aynı rapor, tek isim») koda uygulanmıştı
ama siteye kimse bakmıyordu. Satış sayfasının, ürünün kendisinde olmayan bir rapordan
bahsetmesi en pahalı türden tutarsızlıktır: müşteri onu arar, bulamaz.

Aynı şey ücretsiz/premium bölünmesi için de geçerli — sayfada yanlış tarafta duran bir
sekme, ödeme yapıldıktan sonra ortaya çıkacak bir vaattir.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from domain.lisans import PREMIUM_SEKMELER, UCRETSIZ_SEKMELER

_KOK = Path(__file__).resolve().parent / "web"
_SAYFA = _KOK / "index.html"


def _metin() -> str:
    """HTML kaçışları çözülmüş sayfa — «&amp;» ile «&» aynı sayılsın."""
    return _SAYFA.read_text(encoding="utf-8").replace("&amp;", "&")


class TestSekmeAdlari(unittest.TestCase):
    def test_dokuz_sekme_de_sayfada_gecer(self) -> None:
        govde = _metin()
        for baslik in sorted(UCRETSIZ_SEKMELER | PREMIUM_SEKMELER):
            self.assertIn(baslik, govde,
                          f"«{baslik}» tanıtım sayfasında geçmiyor")

    def test_sayfada_olmayan_sekme_anlatilmiyor(self) -> None:
        """Kaldırılmış/yeniden adlandırılmış sekmeler sayfada kalmasın."""
        govde = _metin()
        gercek = UCRETSIZ_SEKMELER | PREMIUM_SEKMELER
        # Yalnız rapor kartları — «nasıl çalışır» adımları da <li><h3> kullanıyor.
        blok = re.search(r'<ul class="kartlar">(.*?)</ul>', govde, re.S)
        self.assertIsNotNone(blok, "kartlar listesi bulunamadı")
        kartlar = re.findall(r'<h3>(.*?)</h3>', blok.group(1))
        self.assertEqual(len(kartlar), len(gercek), "kart sayısı sekme sayısıyla uyuşmuyor")
        for ad in kartlar:
            self.assertIn(ad, gercek, f"«{ad}» diye bir sekme yok")


class TestPaketBolunmesi(unittest.TestCase):
    def test_premium_kartlar_isaretli(self) -> None:
        """`class="premium"` taşıyan kartlar tam olarak premium sekmeler olmalı."""
        govde = _metin()
        isaretli = set(re.findall(r'<li class="premium"><h3>(.*?)</h3>', govde))
        self.assertEqual(isaretli, set(PREMIUM_SEKMELER))

    def test_paket_listeleri_kodla_ayni(self) -> None:
        """«Ücretsiz» ve «Premium» kutularındaki liste, domain/lisans.py ile birebir."""
        govde = _metin()
        bolum = re.search(r'<div class="paketler">(.*?)\n    </div>', govde, re.S)
        self.assertIsNotNone(bolum, "paketler bölümü bulunamadı")
        kutular = re.findall(r'<div class="paket[^"]*">(.*?)\n      </div>',
                             bolum.group(1), re.S)
        self.assertEqual(len(kutular), 2, "iki paket kutusu bekleniyordu")
        ucretsiz, premium = (set(re.findall(r'<li>(.*?)</li>', k)) for k in kutular)
        self.assertEqual(ucretsiz, set(UCRETSIZ_SEKMELER))
        self.assertEqual(premium, set(PREMIUM_SEKMELER))


class TestSurumVeMetinler(unittest.TestCase):
    def test_surum_kodla_ayni(self) -> None:
        from infra.surum import SURUM
        govde = _SAYFA.read_text(encoding="utf-8")
        self.assertIn(f'"softwareVersion": "{SURUM}"', govde)
        self.assertIn(f"Sürüm {SURUM}", govde)

    def test_json_ld_gecerli(self) -> None:
        """Bozuk JSON-LD sessizce yok sayılır: arama sonucu zenginliği kaybolur."""
        govde = _SAYFA.read_text(encoding="utf-8")
        blob = re.search(r'<script type="application/ld\+json">(.*?)</script>', govde, re.S)
        self.assertIsNotNone(blob)
        json.loads(blob.group(1))

    def test_gizlilik_politikasi_sayfasi_var_ve_bagli(self) -> None:
        """Store başvurusu gizlilik politikası ADRESİ ister; kırık bağlantı reddedilir."""
        sayfa = _KOK / "gizlilik-politikasi.html"
        self.assertTrue(sayfa.is_file(), "gizlilik politikası sayfası yok")
        self.assertIn("/gizlilik-politikasi", _SAYFA.read_text(encoding="utf-8"))
        self.assertIn("gizlilik-politikasi",
                      (_KOK / "sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
