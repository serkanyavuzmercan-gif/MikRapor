"""
Tanıtım sayfası bekçisi — site ile uygulama aynı şeyi söylesin.

NEDEN VAR: sayfa aylarca «Trend & oranlar» diye bir sekmeden bahsetti; uygulamada o
sekmenin adı «Mukayese & Oranlar»dı. Kural 5 («aynı rapor, tek isim») koda uygulanmıştı
ama siteye kimse bakmıyordu. Satış sayfasının, ürünün kendisinde olmayan bir rapordan
bahsetmesi en pahalı türden tutarsızlıktır: müşteri onu arar, bulamaz.

Aynı şey ücretsiz/premium ayrımı için de geçerli — sayfada yanlış tarafta duran bir
kalem, ödeme yapıldıktan sonra ortaya çıkacak bir vaattir.
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
    """
    Sayfa, ürünün SATTIĞI şeyi söylemeli: kilit sekmede değil dışa aktarmada.

    Rapor kartlarında premium işareti olmamalı — dokuz raporun hepsi ücretsiz.
    Sayfada bir raporu premium göstermek, kullanıcının parayla açmaya çalışacağı
    ama zaten açık olan bir şeyi vaat etmektir.
    """

    def _kutular(self) -> tuple[set[str], set[str]]:
        govde = _metin()
        bolum = re.search(r'<div class="paketler">(.*?)\n    </div>', govde, re.S)
        self.assertIsNotNone(bolum, "paketler bölümü bulunamadı")
        kutular = re.findall(r'<div class="paket[^"]*">(.*?)\n      </div>',
                             bolum.group(1), re.S)
        self.assertEqual(len(kutular), 2, "iki paket kutusu bekleniyordu")
        return tuple(set(re.findall(r'<li>(.*?)</li>', k)) for k in kutular)

    def test_rapor_karti_premium_isaretlenmemis(self) -> None:
        self.assertNotIn('class="premium"', _metin(),
                         "dokuz raporun hepsi ücretsiz — kartta premium işareti olmaz")

    def test_premium_kutusu_ucretsiz_sekme_vaat_etmiyor(self) -> None:
        _, premium = self._kutular()
        for ad in UCRETSIZ_SEKMELER:
            self.assertNotIn(ad, premium, f"«{ad}» ücretsiz ama premium kutusunda")

    def test_premium_sekme_premium_kutusunda(self) -> None:
        _, premium = self._kutular()
        for ad in PREMIUM_SEKMELER:
            self.assertIn(ad, premium, f"«{ad}» premium ama kutuda yok")

    def test_disa_aktarim_premium_yaziyor(self) -> None:
        """Gelirin taşıyıcısı bu; sayfada yazmıyorsa kullanıcı sürprizle karşılaşır."""
        _, premium = self._kutular()
        birlesik = " ".join(premium)
        self.assertIn("PDF", birlesik)
        self.assertIn("CSV", birlesik)


class TestGorseller(unittest.TestCase):
    """
    Sayfanın gösterdiği her görsel gerçekten var olmalı.

    Yaşandı: elle yapılan bir deploy'da logo ve paylaşım kartı eksik kaldı; sayfa
    açılıyordu, başlıktaki logo kırık görünüyordu ve bunu kimse otomatik yakalamadı.
    Bir de boyut: 1,8 MB'lık ham görseller yüklendiği gibi sayfaya konursa tanıtım
    sayfası ilk açılışta megabaytlarca indirir.
    """

    _AZAMI_KB = 400

    def _gorseller(self) -> list[str]:
        govde = _SAYFA.read_text(encoding="utf-8")
        return re.findall(r'src="/([^"]+)"', govde)

    def test_her_gorsel_var(self) -> None:
        for ad in self._gorseller():
            with self.subTest(gorsel=ad):
                self.assertTrue((_KOK / ad).is_file(), f"{ad} yok — kırık resim")

    def test_gorseller_makul_boyutta(self) -> None:
        for ad in self._gorseller():
            with self.subTest(gorsel=ad):
                kb = (_KOK / ad).stat().st_size / 1024
                self.assertLess(kb, self._AZAMI_KB,
                                f"{ad} {kb:.0f} KB — sayfaya konmadan küçültülmeli")

    def test_her_gorselin_alt_metni_var(self) -> None:
        """Ekran okuyucu ve görsel yüklenmediğinde tek bilgi kaynağı alt metni."""
        govde = _SAYFA.read_text(encoding="utf-8")
        for etiket in re.findall(r"<img\b[^>]*>", govde):
            with self.subTest(img=etiket[:60]):
                alt = re.search(r'alt="([^"]*)"', etiket)
                self.assertIsNotNone(alt, "alt metni yok")
                self.assertGreater(len(alt.group(1).strip()), 3, "alt metni boş")


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
