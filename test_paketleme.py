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


def spec_datas_blok() -> str:
    """
    Yalnız `datas=[...]` bloğu — EXE(icon=...) farklı bir alandır ve sys._MEIPASS'a
    KOPYALAMAZ, yalnızca .exe dosyasına Windows kaynak ikonu gömer. Tüm dosyayı
    taramak EXE(icon=...) satırındaki referansı "paketlenmiş" sanıp datas'tan
    silinen bir girdiyi kaçırıyordu — bu ayrımı düzeltmeden testler yeşil kalıyordu.
    """
    spec = (_KOK / "MikRapor.spec").read_text(encoding="utf-8")
    m = re.search(r"datas\s*=\s*\[(.*?)\]\s*,?\s*\n", spec, re.S)
    if m is None:
        raise AssertionError("MikRapor.spec içinde `datas=[...]` bloğu bulunamadı")
    return m.group(1)


def spec_assets() -> set[str]:
    """
    datas'ta geçen asset yolları, `assets/` köküne göre — alt klasör KORUNUR.

    Yalnız dosya adını döndürmek `assets\\fonts\\DejaVuSans.ttf`'i `assets/DejaVuSans.ttf`
    sanıp diskte-var kontrolünü yanlış yere bakmaya gönderiyordu.
    """
    ham = re.findall(r"assets\\\\((?:[\w.-]+\\\\)*[\w.-]+\.(?:png|ico|ttf))",
                     spec_datas_blok())
    return {y.replace("\\\\", "/") for y in ham}


class TestSpecAssetKapsami(unittest.TestCase):
    def _spec_assets(self) -> set[str]:
        return spec_assets()

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


class TestKurulumDiziniSaltOkunur(unittest.TestCase):
    """
    Kurulum dizinine ÇALIŞMA ANINDA yazılmaz.

    MSIX'te uygulama `C:\\Program Files\\WindowsApps\\...` altına kurulur ve orası
    yönetici için bile SALT-OKUNURDUR. PyInstaller onefile'da `__file__` geçici
    çıkarma klasörünü gösterdiği ve orası yazılabilir olduğu için bu hata geliştirme
    ve tek-dosya .exe'de HİÇ görünmez — yalnız mağaza paketinde ortaya çıkar.

    Canlı örnek: açılır kutu oku (`chevron-down-teal.png`) yoksa uygulama kendi
    çiziyordu. MSIX'te `QPixmap.save()` istisna atmadan `False` dönüyor, QSS var
    olmayan dosyaya işaret ediyor ve ok büsbütün kayboluyordu. Asset artık derleme
    anında üretiliyor; uygulama yalnız okuyor.

    Yazılabilir yer `%APPDATA%`dır — `infra/config.py: config_dir()`.
    """

    # Pathlib üzerinden yazan metotlar + dosyayı yazmak için açan çağrılar.
    _YAZAN_METOTLAR = {"write_text", "write_bytes", "mkdir", "touch", "unlink",
                       "rmdir", "rename", "replace", "chmod"}
    # Yolu ARGÜMAN olarak alan yazma çağrıları (QPixmap.save(str(p)), open(p, "w")).
    _YAZAN_CAGRILAR = {"save", "open"}

    @staticmethod
    def _kurulum_yolu_adlari(agac) -> set[str]:
        """`Path(__file__)`'dan türeyen isimler — bunlar kurulum dizinini gösterir."""
        import ast

        adlar: set[str] = set()
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Assign):
                continue
            kaynak = ast.dump(dugum.value)
            if "__file__" not in kaynak:
                continue
            for hedef in dugum.targets:
                if isinstance(hedef, ast.Name):
                    adlar.add(hedef.id)
        return adlar

    @classmethod
    def _yazma_ihlalleri(cls, yol: Path) -> list[str]:
        import ast

        agac = ast.parse(yol.read_text(encoding="utf-8"))
        adlar = cls._kurulum_yolu_adlari(agac)
        if not adlar:
            return []

        def kurulum_yolu_mu(dugum) -> bool:
            return any(isinstance(a, ast.Name) and a.id in adlar
                       for a in ast.walk(dugum))

        ihlaller = []
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Call) or not isinstance(dugum.func, ast.Attribute):
                continue
            ad = dugum.func.attr
            # p.write_text(...) / p.parent.mkdir(...)
            if ad in cls._YAZAN_METOTLAR and kurulum_yolu_mu(dugum.func.value):
                ihlaller.append(f"{yol.name}:{dugum.lineno} → .{ad}()")
            # pixmap.save(str(p)) — yol argümanda
            elif ad in cls._YAZAN_CAGRILAR and any(kurulum_yolu_mu(a) for a in dugum.args):
                ihlaller.append(f"{yol.name}:{dugum.lineno} → .{ad}(<kurulum yolu>)")
        return ihlaller

    def test_uygulama_kodu_kurulum_dizinine_yazmaz(self) -> None:
        ihlaller: list[str] = []
        for paket in ("ui", "infra", "domain"):
            for yol in sorted((_KOK / paket).rglob("*.py")):
                ihlaller += self._yazma_ihlalleri(yol)
        self.assertEqual(
            ihlaller, [],
            "Kurulum dizinine çalışma anında yazılıyor — MSIX'te salt-okunur olduğu "
            f"için sessizce bozulur. Yazılabilir yer %APPDATA% (config_dir): {ihlaller}")

    def test_chevron_paketleniyor(self) -> None:
        """Ok artık üretilmiyor, paketten okunuyor — spec'te olmak ZORUNDA."""
        self.assertIn("chevron-down-teal.png", spec_assets(),
                      "chevron-down-teal.png spec'in datas listesinde yok; "
                      "MSIX'te açılır kutu oku kaybolur")


class TestMsixManifest(unittest.TestCase):
    """
    MSIX bildirimi — kimlik Partner Center'dan gelir, uydurulmaz.

    Name/Publisher birebir eşleşmezse Partner Center paketi reddeder. Bu değerler
    gizli değildir (PFN ve Store ID zaten herkese açık), o yüzden repoda dururlar;
    ama YANLIŞLIKLA DEĞİŞTİRİLMELERİ pahalıdır — yükleme reddedilir ve sebebi
    manifest'te tek karakterlik bir fark olur.
    """

    _MANIFEST = _KOK / "packaging" / "AppxManifest.xml"
    _NS = {"d": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
           "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10"}

    def _kok(self):
        import xml.etree.ElementTree as ET
        return ET.parse(self._MANIFEST).getroot()

    def test_kimlik_partner_center_ile_ayni(self) -> None:
        kimlik = self._kok().find("d:Identity", self._NS)
        self.assertEqual(kimlik.get("Name"), "Hidroteknik.Mikrapor")
        self.assertEqual(kimlik.get("Publisher"),
                         "CN=119D3611-306D-4F5E-B28C-3904B4C07374")
        self.assertEqual(kimlik.get("ProcessorArchitecture"), "x64")
        yayinci = self._kok().find("d:Properties/d:PublisherDisplayName", self._NS)
        self.assertEqual(yayinci.text, "Hidroteknik")

    def test_surum_yer_tutucu_kalir(self) -> None:
        """
        Manifest ÜÇÜNCÜ sürüm kaynağı olmaz.

        pyproject.toml ↔ infra/surum.py ikilisini test_surum.py koruyor. Manifest'e
        gerçek sürüm yazılırsa üçüncü kopya doğar ve ikisi ayrışır; sürüm derleme
        sırasında infra/surum.py'den yazılır.
        """
        self.assertEqual(self._kok().find("d:Identity", self._NS).get("Version"),
                         "0.0.0.0",
                         "Manifest'e gerçek sürüm yazılmış — sürüm tek kaynaktan "
                         "(infra/surum.py) derlemede enjekte edilmeli")

    def test_zorunlu_alanlar_dolu(self) -> None:
        """MakeAppx bunlar eksikken paketi üretmez."""
        kok = self._kok()
        for yol in ("d:Properties/d:DisplayName", "d:Properties/d:Description",
                    "d:Properties/d:Logo", "d:Dependencies/d:TargetDeviceFamily",
                    "d:Resources/d:Resource", "d:Applications/d:Application"):
            with self.subTest(alan=yol):
                self.assertIsNotNone(kok.find(yol, self._NS), f"{yol} eksik")
        uygulama = kok.find("d:Applications/d:Application", self._NS)
        self.assertEqual(uygulama.get("EntryPoint"), "Windows.FullTrustApplication")
        gorsel = uygulama.find("uap:VisualElements", self._NS)
        for nitelik in ("DisplayName", "Description", "Square150x150Logo",
                        "Square44x44Logo"):
            with self.subTest(nitelik=nitelik):
                self.assertTrue(gorsel.get(nitelik), f"VisualElements/{nitelik} boş")

    def test_gosterilen_logolar_uretiliyor(self) -> None:
        """Manifest'in adlandırdığı her kutucuk generate_icons.py'den çıkmalı."""
        import re as _re
        metin = self._MANIFEST.read_text(encoding="utf-8")
        istenen = set(_re.findall(r'assets\\([\w.-]+\.png)', metin))
        self.assertTrue(istenen, "manifest'te hiç logo yok — desen bozulmuş olabilir")
        uretici = (_KOK / "assets" / "generate_icons.py").read_text(encoding="utf-8")
        eksik = {a for a in istenen if a not in uretici}
        self.assertFalse(eksik, f"Manifest bu kutucukları istiyor ama "
                                f"generate_icons.py üretmiyor: {sorted(eksik)}")


class TestSpecIkiBicim(unittest.TestCase):
    """
    Tek spec, iki çıktı biçimi: onefile (doğrudan indirme) + onedir (MSIX gövdesi).

    İkinci bir spec dosyası açmak asset listesinin sessizce ayrışması demekti —
    tam da test_paketleme'nin var olma sebebi.
    """

    def test_onedir_anahtari_ve_collect_duruyor(self) -> None:
        spec = (_KOK / "MikRapor.spec").read_text(encoding="utf-8")
        self.assertIn("MIKRAPOR_ONEDIR", spec,
                      "onedir anahtarı kaldırılmış — MSIX gövdesi üretilemez")
        self.assertIn("COLLECT(", spec,
                      "COLLECT yok — onedir modu klasör üretmez")
        self.assertIn("exclude_binaries=ONEDIR", spec,
                      "onedir'de binaries EXE'ye gömülürse COLLECT ile çakışır")

    def test_datas_bloku_her_iki_bicimde_de_okunabiliyor(self) -> None:
        """Yapı değişikliği asset bekçisini kör etmemeli."""
        self.assertTrue(spec_assets(), "datas bloğu okunamıyor — bekçi körleşti")


if __name__ == "__main__":
    unittest.main()
