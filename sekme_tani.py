"""
Sekme cubugu teshisi -- Windows'ta gercekte ne oluyor?

ASCII-ONLY ciktisi: Windows konsolu cp1252 kullaniyor ve Turkce karakterde
UnicodeEncodeError ile cokuyor. Teshis aracinin kendisi cokerse hicbir sey
ogrenemiyoruz; ilk denemede tam bunu yaptik.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from ui.styles import APP_STYLESHEET  # noqa: E402

app.setStyleSheet(APP_STYLESHEET)
from ui.app import HeaderTabBar, MikRaporWindow  # noqa: E402


def slug(s: str) -> str:
    """Turkce karakterleri ASCII'ye indir -- konsol cokmesin."""
    tablo = str.maketrans("ıİşŞğĞüÜöÖçÇâÂ", "iIsSgGuUoOcCaA")
    return s.translate(tablo).encode("ascii", "replace").decode()


print("font:", slug(app.font().family()), app.font().pointSize())
w = MikRaporWindow()
w.resize(960, 840)
w.show()
for _ in range(12):
    app.sendPostedEvents()
    app.processEvents()
tb = w._tab_bar
ust = tb.parentWidget()
print(f"pencere={w.width()} nav={ust.width() if ust else -1} cubuk={tb.width()}")
print(f"secilen: font={tb._font_px}px dolgu={tb._dolgu}px")
print(f"kullanilabilir_en={tb._kullanilabilir_en()}")
print("aday hesaplari:")
for px, d in HeaderTabBar._OLCEK_ADAYLARI:
    t = sum(tb._sekme_genisligi(i, px, d) for i in range(tb.count()))
    print(f"  ({px},{d}) -> {t}")
print("gercek tabRect:")
for i in range(tb.count()):
    r = tb.tabRect(i)
    print(f"  {i} {slug(tb.tabText(i).replace('&&', '&')):22s} "
          f"hesap={tb._sekme_genisligi(i, tb._font_px, tb._dolgu):4d} "
          f"gercek={r.width():4d} sag={r.right():5d}")
w.close()
