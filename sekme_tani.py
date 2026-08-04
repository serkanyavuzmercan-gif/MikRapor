"""Sekme çubuğu teşhisi — Windows'ta gerçekte ne oluyor?"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from ui.styles import APP_STYLESHEET
app.setStyleSheet(APP_STYLESHEET)
from ui.app import HeaderTabBar, MikRaporWindow

print("Varsayılan font:", app.font().family(), app.font().pointSize())
w = MikRaporWindow(); w.resize(960, 840); w.show()
for _ in range(12):
    app.sendPostedEvents(); app.processEvents()
tb = w._tab_bar
ust = tb.parentWidget()
print(f"pencere={w.width()} nav={ust.width() if ust else '?'} cubuk={tb.width()}")
print(f"secilen olcek: font={tb._font_px}px dolgu={tb._dolgu}px")
print(f"_kullanilabilir_en()={tb._kullanilabilir_en()}")
print("her adayin hesaplanan toplami:")
for px, d in HeaderTabBar._OLCEK_ADAYLARI:
    t = sum(tb._sekme_genisligi(i, px, d) for i in range(tb.count()))
    print(f"   ({px},{d}) -> {t}")
print("GERCEK tabRect genislikleri:")
toplam = 0
for i in range(tb.count()):
    r = tb.tabRect(i)
    toplam += r.width()
    print(f"   {i} {tb.tabText(i).replace('&&','&'):22s} hesap="
          f"{tb._sekme_genisligi(i, tb._font_px, tb._dolgu):4d} gercek={r.width():4d} sag={r.right():5d}")
print(f"gercek toplam={toplam}")
w.close()
