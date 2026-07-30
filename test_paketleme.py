"""
PyInstaller paketleme bütünlüğü — MikRapor.spec kaynaktaki her assetle senkron mu?

Bir sekmenin HERO_ASSET'i assets/ klasöründe durur ama .spec'in `datas` listesine
eklenmezse, kaynaktan (`python main.py`) çalıştırıldığında hiçbir sorun görünmez —
geliştirici hep kaynaktan çalıştırır. Ama PyInstaller ile derlenen .exe'ye dosya hiç
girmez; müşteriye giden pakette o sekmenin boş-durum görseli sessizce eksik kalır ve
varsayılana (anasayfalogo.png) düşer. Canlıda 7 sekmenin hero'su (ai.png dahil) bu
şekilde eksikti — kimse fark etmemişti çünkü herkes kaynaktan test ediyordu.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_KOK = Path(__file__).parent

# app_icon() / app_logo_pixmap() bu sırayla diskte arar (ui/resources.py). Pencere
# ikonu / görev çubuğu logosu — "generic çıkıyor" şikâyeti tam bunların eksik
# paketlenmesinden gelir: dosya bulunamayınca QIcon() boş döner, Qt kendi
# varsayılan (jenerik) ikonuna düşer. Kaynaktan (`python main.py`) çalıştırınca
# hiç fark edilmez çünkü assets/ zaten yanı başındadır.
_MARKA_DOSYALARI = ("icon.ico", "logo.png", "logo-mark.png")


class TestSpecAssetKapsami(unittest.TestCase):
    def _spec_datas_blok(self) -> str:
        """
        Yalnız `datas=[...]` bloğu — EXE(icon=...) farklı bir alandır ve sys._MEIPASS'a
        KOPYALAMAZ, yalnızca .exe dosyasına Windows kaynak ikonu gömer. Tüm dosyayı
        taramak EXE(icon=...) satırındaki referansı "paketlenmiş" sanıp datas'tan
        silinen bir girdiyi kaçırıyordu — bu ayrımı düzeltmeden testler yeşil kalıyordu.
        """
        spec = (_KOK / "MikRapor.spec").read_text(encoding="utf-8")
        m = re.search(r"datas\s*=\s*\[(.*?)\]\s*,?\s*\n", spec, re.S)
        self.assertIsNotNone(m, "MikRapor.spec içinde `datas=[...]` bloğu bulunamadı")
        return m.group(1)

    def _spec_assets(self) -> set[str]:
        return set(re.findall(r"assets\\\\([\w.-]+\.(?:png|ico))", self._spec_datas_blok()))

    def _kod_hero_assetleri(self) -> set[str]:
        assetler: set[str] = set()
        for yol in (_KOK / "ui" / "tabs").glob("*_tab.py"):
            metin = yol.read_text(encoding="utf-8")
            assetler.update(re.findall(r'HERO_ASSET\s*=\s*"([\w.-]+\.png)"', metin))
        return assetler

    def test_her_sekmenin_hero_gorseli_spec_datasinda(self) -> None:
        kullanilan = self._kod_hero_assetleri()
        self.assertTrue(kullanilan, "hiç HERO_ASSET bulunamadı — glob deseni bozulmuş olabilir")
        paketlenen = self._spec_assets()
        eksik = kullanilan - paketlenen
        self.assertFalse(
            eksik,
            f"Bu hero görselleri koddan kullanılıyor ama MikRapor.spec'in `datas` "
            f"listesinde yok — derlenmiş .exe'de eksik kalır: {sorted(eksik)}")

    def test_marka_dosyalari_spec_datasinda(self) -> None:
        """Pencere ikonu + görev çubuğu logosu — jenerik ikona düşmenin kaynağı."""
        eksik = set(_MARKA_DOSYALARI) - self._spec_assets()
        self.assertFalse(
            eksik,
            f"app_icon()/app_logo_pixmap()'ın okuduğu dosyalar spec'te eksik, "
            f"derlenmiş .exe'de pencere ikonu jenerik çıkar: {sorted(eksik)}")

    def test_exe_dosya_ikonu_da_ayarli(self) -> None:
        """EXE(icon=...) — Explorer'da görünen .exe dosya ikonu, ayrı bir alan."""
        spec = (_KOK / "MikRapor.spec").read_text(encoding="utf-8")
        self.assertIn("icon=['assets\\\\icon.ico']", spec.replace(" ", ""))

    def test_spec_teki_her_asset_diskte_var(self) -> None:
        """Ters yön: spec, artık var olmayan bir dosyaya işaret etmesin."""
        for ad in self._spec_assets():
            self.assertTrue(
                (_KOK / "assets" / ad).exists(),
                f"MikRapor.spec '{ad}' diyor ama assets/{ad} diskte yok")


if __name__ == "__main__":
    unittest.main()
