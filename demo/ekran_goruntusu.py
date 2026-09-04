"""
Mağaza ekran görüntülerini üretir:  python -m demo.ekran_goruntusu [klasör]

NEDEN ELLE DEĞİL DE BETİK: Store'a giden kare her sürümde yeniden çekilecek ve
elle çekilen karede pencere boyutu, seçili tarih aralığı ve hangi sekmenin
görüneceği her seferinde biraz kayar. Betik hepsini sabitler; kare farkı gerçek
bir arayüz değişikliğidir.

BOYUT: 1600×1000 — Store asgarisi 1366×768'in üstünde ve uygulamanın kendi
öntanımlı 1220×840'ı o asgarinin ALTINDA kalıyor (bkz. demo/calistir.py).

Rapor, worker THREAD'i beklemeden üretilir: iş fonksiyonu doğrudan çağrılıp sonuç
sekmenin kendi `_on_bitti`sine verilir. Offscreen koşuda iş parçacığı beklemek
kilitlenme riski taşır; ekranda görünen widget yine sekmenin GERÇEK çizim yolu.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

GENISLIK, YUKSEKLIK = 1600, 1000

# (sekme sınıfı adı, dosya adı) — satın alma kararını veren sırayla.
KARELER = (
    ("TahsilatAlacakTab", "01-alacak-borc"),
    ("NakitAkisTab", "02-nakit-akis"),
    ("BilancoTab", "03-bilanco"),
    ("TrendTab", "04-mukayese-oranlar"),
    ("GercekDurumTab", "05-nakit-karlilik"),
    ("GelirTablosuTab", "06-gelir-tablosu"),
    ("TahminTab", "07-tahmin"),
    ("ReelDegerTab", "08-reel-deger"),
)


def uret(hedef: Path, bas: str = "", bit: str = "") -> list[Path]:
    from PyQt6.QtWidgets import QApplication

    uygulama = QApplication.instance() or QApplication(sys.argv)

    import ui.app as app_mod
    from demo.baglayici import demo_cfg, demo_moduna_gec
    from ui.styles import APP_STYLESHEET

    demo_moduna_gec()
    uygulama.setStyleSheet(APP_STYLESHEET)

    pencere = app_mod.MikRaporWindow()
    pencere.resize(GENISLIK, YUKSEKLIK)
    pencere.show()

    cfg = demo_cfg()
    bas = bas or pencere._donem.bas_tarih().toString("yyyy-MM-dd")   # noqa: SLF001
    bit = bit or pencere._donem.bit_tarih().toString("yyyy-MM-dd")   # noqa: SLF001

    hedef.mkdir(parents=True, exist_ok=True)
    yazilan: list[Path] = []
    for sinif_adi, dosya in KARELER:
        sinif = getattr(app_mod, sinif_adi)
        indeks = _sekme_indeksi(pencere, sinif)
        if indeks is None:
            print(f"ATLANDI {sinif_adi} — pencerede yok", file=sys.stderr)
            continue
        pencere._tab_bar.setCurrentIndex(indeks)      # noqa: SLF001
        sekme = pencere._stack.widget(indeks)         # noqa: SLF001
        uygulama.processEvents()

        sonuc = sekme._is_hazirla(cfg, bas, bit)(lambda m: None)   # noqa: SLF001
        sekme._on_bitti(sonuc)                                     # noqa: SLF001
        uygulama.processEvents()

        yol = hedef / f"{dosya}.png"
        pencere.grab().save(str(yol))
        yazilan.append(yol)
        print(f"{yol}  ({GENISLIK}x{YUKSEKLIK})")
    return yazilan


def _sekme_indeksi(pencere, sinif) -> int | None:
    for i in range(pencere._stack.count()):           # noqa: SLF001
        if isinstance(pencere._stack.widget(i), sinif):  # noqa: SLF001
            return i
    return None


if __name__ == "__main__":
    klasor = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ekran-goruntuleri")
    uret(klasor)
