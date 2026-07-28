"""
Veritabanı kataloğu — hangi yıl hangi Mikro veritabanında?

Mikro'da veritabanını FİRMA KODU seçer; `calisma_yili` yalnız auth gövdesinde gider.
Canlı kurulumda firma 20 → 2020-2025, firma 26 → 2026 (ileride 2030'a kadar). Kullanıcı
tarih aralığını seçer; hangi yılın nerede olduğunu program bulmalı.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from infra.config import MikroConfig
from infra.veritabani import (
    FirmaKapsami,
    firma_client,
    firma_kodlari,
    katalog,
    onbellegi_temizle,
    yil_icin_firma,
    yillari_firmalara_dagit,
)

_CFG = MikroConfig(
    base_url="https://ornek.local", api_key="k", firma_kodu="26",
    firma_kodlari="20, 26", calisma_yili=2026, kullanici_kodu="u", sifre_gun="s",
)


class TestFirmaKodlari(unittest.TestCase):
    def test_virgullu_liste(self) -> None:
        self.assertEqual(firma_kodlari(_CFG), ["20", "26"])

    def test_bosluk_ve_noktali_virgul(self) -> None:
        cfg = MikroConfig(firma_kodu="1", firma_kodlari="20; 26  31")
        self.assertEqual(firma_kodlari(cfg), ["20", "26", "31"])

    def test_sayisal_aralik_basindaki_sifiri_korur(self) -> None:
        cfg = MikroConfig(firma_kodu="1", firma_kodlari="001-003, 10")
        self.assertEqual(firma_kodlari(cfg), ["001", "002", "003", "10"])

    def test_cok_buyuk_aralik_genisletilmez(self) -> None:
        cfg = MikroConfig(firma_kodu="1", firma_kodlari="001-999")
        self.assertEqual(firma_kodlari(cfg), ["001-999"])

    def test_tekrarlar_elenir_sira_korunur(self) -> None:
        cfg = MikroConfig(firma_kodu="1", firma_kodlari="26, 20, 26")
        self.assertEqual(firma_kodlari(cfg), ["26", "20"])

    def test_bos_liste_tek_firmaya_duser(self) -> None:
        """Tek veritabanlı kurulum bozulmamalı — ayar boş kalabilir."""
        cfg = MikroConfig(firma_kodu="20")
        self.assertEqual(firma_kodlari(cfg), ["20"])

    def test_firma_kodu_da_yoksa_bos(self) -> None:
        self.assertEqual(firma_kodlari(MikroConfig()), [])


class TestFirmaClient(unittest.TestCase):
    def test_yalniz_firma_kodu_degisir(self) -> None:
        c = firma_client(_CFG, "20")
        self.assertEqual(c.cfg.firma_kodu, "20")
        self.assertEqual(c.cfg.base_url, "https://ornek.local")
        self.assertEqual(c.cfg.calisma_yili, 2026)

    def test_kaynak_cfg_degismez(self) -> None:
        firma_client(_CFG, "20")
        self.assertEqual(_CFG.firma_kodu, "26")


class TestKatalog(unittest.TestCase):
    def setUp(self) -> None:
        onbellegi_temizle()
        self.addCleanup(onbellegi_temizle)

    @staticmethod
    def _araliklar(esleme: dict[str, tuple[int, int]]):
        def sahte(client):
            return esleme.get(client.cfg.firma_kodu, (0, 0))
        return patch("infra.veritabani.fetch_yil_araligi", side_effect=sahte)

    def test_her_firma_kendi_araligini_verir(self) -> None:
        with self._araliklar({"20": (2020, 2025), "26": (2026, 2026)}):
            k = katalog(_CFG)
        self.assertEqual([(x.firma_kodu, x.ilk_yil, x.son_yil) for x in k],
                         [("20", 2020, 2025), ("26", 2026, 2026)])

    def test_bos_veritabani_kataloga_girmez(self) -> None:
        with self._araliklar({"20": (2020, 2025), "26": (0, 0)}):
            k = katalog(_CFG)
        self.assertEqual([x.firma_kodu for x in k], ["20"])

    def test_okunamayan_firma_raporu_dusurmez(self) -> None:
        """Erişilemeyen bir veritabanı yüzünden rapor komple düşmemeli."""
        from infra.mikro_api import MikroAPIError

        def bazen_patla(client):
            if client.cfg.firma_kodu == "26":
                raise MikroAPIError("veritabanı yok")
            return (2020, 2025)

        with patch("infra.veritabani.fetch_yil_araligi", side_effect=bazen_patla):
            k = katalog(_CFG)
        self.assertEqual([x.firma_kodu for x in k], ["20"])

    def test_onbellek_ikinci_kez_yoklamaz(self) -> None:
        """Her rapor için yeniden yoklamak israf; kapsam süreç boyunca sabittir."""
        with self._araliklar({"20": (2020, 2025), "26": (2026, 2026)}) as m:
            katalog(_CFG)
            katalog(_CFG)
        self.assertEqual(m.call_count, 2)          # 2 firma × 1 kez

    def test_onbellek_temizlenince_yeniden_yoklanir(self) -> None:
        with self._araliklar({"20": (2020, 2025), "26": (2026, 2026)}) as m:
            katalog(_CFG)
            onbellegi_temizle()
            katalog(_CFG)
        self.assertEqual(m.call_count, 4)


class TestYilEslemesi(unittest.TestCase):
    KAPSAM = [FirmaKapsami("20", 2020, 2025), FirmaKapsami("26", 2026, 2030)]

    def test_yil_kendi_veritabanina_gider(self) -> None:
        self.assertEqual(yil_icin_firma(self.KAPSAM, 2023), "20")
        self.assertEqual(yil_icin_firma(self.KAPSAM, 2026), "26")

    def test_kapsam_disi_yil_bos_doner(self) -> None:
        self.assertEqual(yil_icin_firma(self.KAPSAM, 2019), "")
        self.assertEqual(yil_icin_firma(self.KAPSAM, 2031), "")

    def test_cakisan_kapsamda_ilk_sira_kazanir(self) -> None:
        """Devir yılında iki veritabanında da veri olur; sırayı kullanıcı belirler."""
        kapsam = [FirmaKapsami("26", 2025, 2030), FirmaKapsami("20", 2020, 2025)]
        self.assertEqual(yil_icin_firma(kapsam, 2025), "26")

    def test_dagitim_kapsam_disini_atar(self) -> None:
        out = yillari_firmalara_dagit(self.KAPSAM, [2019, 2023, 2026, 2035])
        self.assertEqual(out, {2023: "20", 2026: "26"})


class TestYilClientEntegrasyonu(unittest.TestCase):
    """Mukayese, yılı doğru VERİTABANINDAN okumalı — asıl kazanç burada."""

    def setUp(self) -> None:
        onbellegi_temizle()
        self.addCleanup(onbellegi_temizle)

    def test_gecmis_yil_eski_veritabanindan_okunur(self) -> None:
        from infra.mukayese_fetch import yil_client
        with patch("infra.veritabani.fetch_yil_araligi",
                   side_effect=lambda c: {"20": (2020, 2025)}.get(c.cfg.firma_kodu, (2026, 2026))):
            c = yil_client(_CFG, 2023)
        self.assertEqual(c.cfg.firma_kodu, "20")
        self.assertEqual(c.cfg.calisma_yili, 2023)

    def test_kapsam_disi_yilda_rapor_durur(self) -> None:
        """
        Katalog DOLU ama yıl hiçbir kapsamda değil → başka firmaya düşmek yasak.

        Birden çok veritabanı varken yanlışını seçmek sessizce yanlış rakam üretir;
        canlıda 2023'ü firma 26'da aramak tam olarak buydu.
        """
        from infra.mukayese_fetch import YilVeritabaniHatasi, yil_client
        with patch("infra.veritabani.fetch_yil_araligi",
                   side_effect=lambda c: {"20": (2020, 2025)}.get(c.cfg.firma_kodu, (2026, 2026))):
            with self.assertRaises(YilVeritabaniHatasi):
                yil_client(_CFG, 2019)

    def test_katalog_bosken_secili_firmayla_devam(self) -> None:
        """
        Katalog hiç kurulamadıysa durmak yanlış: seçenek tek, yanlışını seçmek imkânsız.

        Geçici bir ağ hatasında programın komple kullanılamaz olmaması için.
        """
        from infra.mukayese_fetch import yil_client
        cfg = MikroConfig(base_url="https://x", api_key="k", firma_kodu="20",
                          calisma_yili=2025, kullanici_kodu="u", sifre_gun="s")
        with patch("infra.veritabani.fetch_yil_araligi", return_value=(0, 0)):
            c = yil_client(cfg, 2021)
        self.assertEqual(c.cfg.firma_kodu, "20")
        self.assertEqual(c.cfg.calisma_yili, 2021)


class TestSekmelerYilaGore(unittest.TestCase):
    """
    Her rapor sekmesi, dönemin bittiği yılın veritabanına bağlanmalı.

    Ayarlarda «20, 26» yazılıyken firma kodu listenin İLKİNDEN türetiliyor (20).
    Sekmeler doğrudan MikroClient(cfg) kurarsa 2026 raporu 2020-2025 veritabanından
    okunur ve boş/yanlış çıkar. Bu testin amacı o yolu kapalı tutmak.
    """

    def test_hicbir_sekme_dogrudan_istemci_kurmaz(self) -> None:
        import pathlib as _p
        suclu = [y.name for y in sorted(_p.Path("ui/tabs").glob("*_tab.py"))
                 if "MikroClient(cfg)" in y.read_text(encoding="utf-8")]
        self.assertEqual(suclu, [], "yil_client kullanılmalı: " + ", ".join(suclu))

    def test_teshis_araclari_da_yil_client_kullanir(self) -> None:
        """
        CLI'lar da aynı yolu kullanmalı.

        Canlıda `stok_diag_cli.py` seçili firmayla (20 → 2020-2025) bağlanıp 2026
        dönemini sorguladı ve her rakamı 0,00 bastı. Teşhis aracı yanlış veritabanını
        okuyorsa teşhisin kendisi yanıltıcı olur.
        """
        import pathlib as _p
        suclu = [y.name for y in sorted(_p.Path(".").glob("*_cli.py"))
                 if "MikroClient(cfg)" in y.read_text(encoding="utf-8")]
        self.assertEqual(suclu, [], "yil_client kullanılmalı: " + ", ".join(suclu))

    def test_ilk_kod_secili_yila_ait_olmayabilir(self) -> None:
        """«20, 26» yazan kullanıcıda türetilen firma kodu 20'dir — 2026 raporu için yanlış."""
        cfg = MikroConfig(base_url="https://x", api_key="k", firma_kodlari="20, 26",
                          kullanici_kodu="u", sifre_gun="s").normalized()
        self.assertEqual(cfg.firma_kodu, "20")
        from infra.mukayese_fetch import yil_client
        with patch("infra.veritabani.fetch_yil_araligi",
                   side_effect=lambda c: {"20": (2020, 2025)}.get(c.cfg.firma_kodu, (2026, 2026))):
            self.assertEqual(yil_client(cfg, 2026).cfg.firma_kodu, "26")
            self.assertEqual(yil_client(cfg, 2023).cfg.firma_kodu, "20")


if __name__ == "__main__":
    unittest.main()
