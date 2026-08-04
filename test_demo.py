"""
Demo modu bekçileri.

İKİ AYRI ŞEYİ KORUR:
  1. Demo, uygulamanın GERÇEK yolunu koşturuyor mu? (imza + dolu sonuç)
  2. Demo, mağazaya giden pakete ya da kullanıcının kurulumuna SIZIYOR mu?

«İmza aynı» testi tek başına yetmez: demo `fetch_mizan` anahtarı `hesap_kodu`
yerine `hesap` yazsa imza yeşil kalır, ekran boş çıkar — «bakılamayan temiz
sayılmaz» kuralının demo karşılığı. Bu yüzden asıl bekçi, demo satırlarını GERÇEK
domain motorlarından geçirip sonucun dolu ve tutarlı olduğunu sınar.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import unittest

BAS, BIT = "2026-01-01", "2026-06-30"


class TestImzaUyumu(unittest.TestCase):
    """Demo fetch imzaları gerçeğiyle aynı mı? Ayrışırsa demo başka bir yol koşar."""

    def test_parametre_adlari_ve_sirasi_ayni(self) -> None:
        from demo import fetch as demo_fetch
        from infra import mikro_fetch

        for ad in sorted(a for a in dir(demo_fetch) if a.startswith("fetch_")):
            with self.subTest(fetch=ad):
                gercek = getattr(mikro_fetch, ad, None)
                self.assertIsNotNone(gercek, f"{ad} infra.mikro_fetch'te yok — demo bayatlamış")
                # Annotation'lar KARŞILAŞTIRILMAZ (demo `Any` alır); ad ve sıra yeter.
                d = list(inspect.signature(getattr(demo_fetch, ad)).parameters.values())
                g = list(inspect.signature(gercek).parameters.values())
                self.assertEqual([p.name for p in d], [p.name for p in g])
                self.assertEqual([p.kind for p in d], [p.kind for p in g])


class TestDefterTutarli(unittest.TestCase):
    """Demo satırları GERÇEK domain motorlarından geçince anlamlı tablo çıkıyor mu?"""

    def test_bilanco_dengede_ve_dolu(self) -> None:
        from demo.fetch import fetch_mizan
        from domain.mizan_bilanco import build_bilanco

        b = build_bilanco(fetch_mizan(None, BIT), asof=BIT)
        self.assertGreater(b.aktif_toplam, 0.0, "demo mizanı boş bilanço üretiyor")
        self.assertAlmostEqual(b.aktif_toplam, b.pasif_toplam, delta=max(1.0, b.aktif_toplam * 1e-6))

    def test_gelir_tablosu_kar_uretiyor(self) -> None:
        from demo.fetch import fetch_gelir_tablosu
        from domain.gelir_tablosu import build_gelir_tablosu

        gt = build_gelir_tablosu(fetch_gelir_tablosu(None, BAS, BIT), bas=BAS, bit=BIT)
        self.assertGreater(gt.net_satislar, 0.0)
        self.assertGreater(gt.brut_kar, 0.0)

    def test_nakit_detay_toplami_ozetle_tutuyor(self) -> None:
        """Kural 3c: «özet 3M diyor, döküm 2,8M» hiç detay olmamasından KÖTÜDÜR."""
        from demo.fetch import fetch_nakit_akis_detay, fetch_nakit_akis_gl

        ozet = fetch_nakit_akis_gl(None, BAS, BIT)
        for tip in (0, 1):
            beklenen = sum(r["tutar"] for r in ozet if r["tip"] == tip)
            detay = sum(r["tutar"] for r in fetch_nakit_akis_detay(None, BAS, BIT, tip))
            self.assertAlmostEqual(detay, beklenen, delta=max(1.0, beklenen * 1e-6),
                                   msg=f"tip={tip} detayı özetle tutmuyor")

    def test_acik_kalemler_yaslandirma_uretiyor(self) -> None:
        from demo.fetch import fetch_acik_kalemler, fetch_cari_vade_gun
        from domain.tahsilat_alacak import build_tahsilat_alacak

        ta = build_tahsilat_alacak(
            fetch_acik_kalemler(None, BIT, BAS, BIT), bas=BAS, bit=BIT,
            vade_gun_map=fetch_cari_vade_gun(None))
        self.assertGreater(ta.alacak_toplam, 0.0, "demo açık kalemleri alacak üretmiyor")
        self.assertGreater(ta.borc_toplam, 0.0, "demo açık kalemleri borç üretmiyor")
        self.assertTrue(ta.top_alacak, "en çok alacaklı cari listesi boş")
        self.assertGreater(ta.donem_tahsilat, 0.0, "dönem tahsilatı sıfır — DSO ölçülemez")

    def test_defter_secilen_araligin_disina_cikmaz(self) -> None:
        """Kural 1: aralık dışından tek gün bile veri gelmez."""
        from demo.fetch import fetch_stok_aylik

        aylar = [r["ay"] for r in fetch_stok_aylik(None, "2026-03-01", "2026-05-31")]
        self.assertEqual(aylar, ["2026-03", "2026-04", "2026-05"])


class TestSizintiYok(unittest.TestCase):
    """Kurgu rakam ne pakete ne kullanıcının kurulumuna sızar."""

    def test_uygulama_kodu_demoyu_import_etmiyor(self) -> None:
        """
        `ui/`, `infra/`, `domain/` ve `main.py` demoyu TANIMAZ.

        Koşullu bir import bile yeterdi: PyInstaller koşullu import'u da statik
        izler, `demo/` pakete girer ve kurgu rakamların kullanıcıya ulaşmaması
        `excludes` listesinin doğruluğuna bağlı kalırdı.
        """
        kok = pathlib.Path(__file__).resolve().parent
        hedefler = [kok / "main.py"]
        for paket in ("ui", "infra", "domain"):
            hedefler.extend((kok / paket).rglob("*.py"))
        for p in hedefler:
            with self.subTest(dosya=p.name):
                agac = ast.parse(p.read_text(encoding="utf-8"))
                for n in ast.walk(agac):
                    ad = ""
                    if isinstance(n, ast.Import):
                        ad = " ".join(a.name for a in n.names)
                    elif isinstance(n, ast.ImportFrom):
                        ad = n.module or ""
                    self.assertFalse(ad.startswith("demo"),
                                     f"{p} demoyu import ediyor — paket sızıntısı riski")

    def test_lisans_okuyucusu_yamalanmiyor(self) -> None:
        """
        `lisans_durumu` SAHİP döndürmek YASAK.

        O yol `premium_durumu` içinde `premium_onbellek_yaz()` tetikler ve kural 8
        gereği kullanıcının GERÇEK config'i kalıcı premium olurdu.
        """
        kaynak = (pathlib.Path(__file__).resolve().parent / "demo" / "baglayici.py").read_text()
        agac = ast.parse(kaynak)
        atanan = {
            n.targets[0].attr
            for n in ast.walk(agac)
            if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Attribute)
        }
        self.assertNotIn("lisans_durumu", atanan)
        self.assertNotIn("premium_onbellek", atanan)

    def test_demo_config_gercek_klasore_yazmaz(self) -> None:
        import infra.config as config_mod
        from demo.baglayici import _config_izole_et

        gercek = config_mod.config_dir()
        try:
            demo_klasor = _config_izole_et()
            self.assertNotEqual(demo_klasor.resolve(), gercek.resolve())
            self.assertEqual(config_mod.config_dir().resolve(), demo_klasor.resolve())
        finally:
            importlib_reload(config_mod)

    def test_demo_paketi_spec_disinda(self) -> None:
        kok = pathlib.Path(__file__).resolve().parent
        spec = (kok / "MikRapor.spec").read_text(encoding="utf-8")
        self.assertNotIn("demo", spec.replace("demolar", ""),
                         "spec demo paketini topluyor olabilir")


def importlib_reload(modul) -> None:
    import importlib
    importlib.reload(modul)


if __name__ == "__main__":
    unittest.main()
