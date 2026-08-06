"""
PyQt6 KURULU DEĞİLKEN de bütün testler koşabilmeli.

NEDEN VAR: CI ubuntu'da PyQt6 kurulu değil, geliştirme makinesinde kurulu. Bir
bekçi kaynağı almak için `ui.rapor_tab`ı import etti — o modül PyQt6 çekiyor ve
CI `ModuleNotFoundError` ile düştü. Yerelde 659 test yeşildi; arıza yalnız
push'tan sonra, dakikalar sonra görüldü. **İki kez oldu**: bir kez düzeltildi,
sonraki turda aynı yoldan geri geldi.

Kural gereği ikinci başarısızlıkta tahmin bırakılır, ölçüm konur: burada PyQt6
importu gerçekten engellenir ve suite alt süreçte koşturulur. `skipUnless`
saymak ya da import satırı grep'lemek yetmez — arıza METOT GÖVDESİNDEKİ bir
import'tan geliyordu, yani yalnız o metot koşarken ortaya çıkıyor.

Bu test PyQt6 KURULUYKEN koşar. Kurulu değilse zaten gerçek koşunun kendisi bu
ölçümdür; ikinci kez koşturmak boşuna.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

_KOK = Path(__file__).resolve().parent
_OZYINELEME = "MIKRAPOR_PYQTSIZ"

# Alt süreçte koşan program: PyQt6'yı meta_path'ten engelle, sonra suite'i topla
# ve koştur. `find_spec` içinde ImportError atmak, paketin hiç kurulu olmamasıyla
# aynı sonucu verir — sanal ortam kurmaya gerek yok.
_ALT_SUREC = """
import sys, unittest


class _PyQt6Yok:
    def find_spec(self, ad, yol=None, hedef=None):
        if ad == "PyQt6" or ad.startswith("PyQt6."):
            raise ImportError("PyQt6 yok (bekci taklidi)")
        return None


sys.meta_path.insert(0, _PyQt6Yok())
for ad in [a for a in sys.modules if a == "PyQt6" or a.startswith("PyQt6.")]:
    del sys.modules[ad]

yukleyici = unittest.defaultTestLoader
suite = yukleyici.discover(".", pattern="test_*.py")
if yukleyici.errors:
    print("TOPLAMA HATASI:", *yukleyici.errors, sep="\\n")
    sys.exit(2)
sonuc = unittest.TextTestRunner(verbosity=0).run(suite)
sys.exit(0 if sonuc.wasSuccessful() else 1)
"""


@unittest.skipIf(os.environ.get(_OZYINELEME), "alt süreç — kendini çağırmasın")
class TestPyQtsizKosu(unittest.TestCase):
    def test_suite_pyqt6_olmadan_da_yesil(self) -> None:
        try:
            import PyQt6  # noqa: F401
        except ImportError:
            self.skipTest("PyQt6 zaten yok — gerçek koşu bu ölçümün kendisi")

        ortam = dict(os.environ, **{_OZYINELEME: "1", "PYTHONIOENCODING": "utf-8"})
        p = subprocess.run(
            [sys.executable, "-c", _ALT_SUREC],
            cwd=_KOK, env=ortam, capture_output=True, text=True, timeout=900,
        )
        if p.returncode != 0:
            # Sebep ÇIKTIDA yazar: «düştü» demek hangi testin neden düştüğünü
            # söylemez ve kullanıcı (burada: geliştirici) aramak zorunda kalır.
            kuyruk = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
            self.fail(
                "PyQt6 kurulu değilken suite düşüyor — CI'da da düşecek.\n"
                "Kaynak okuyan bekçiler modülü İMPORT ETMEMELİ "
                "(bkz. test_lisans._kaynak).\n\n" + kuyruk)


if __name__ == "__main__":
    unittest.main()
