"""
Demo modunun giriş noktası:  python -m demo.calistir

Uygulama kodunda demoya ait tek satır yoktur (bkz. `demo/__init__.py`); yamalar
burada, `ui.app` import edildikten SONRA kurulur.

PENCERE BOYUTU BURADA ZORLANIR. Uygulamanın kendi açılışı ekranın %80'i kadardır
(`ui/app.py: _ekrani_orantili_ac`) ve öntanımlı `resize(1220, 840)` Microsoft
Store'un ekran görüntüsü asgarisi olan **1366×768'in altındadır** — küçük ekranlı
bir dizüstünde çekilen kare mağaza tarafından reddedilir. Ayrıca 1220px'te sekme
çubuğu daralma yoluna giriyor ve etiketler «Tahmin & Proj…» diye kısalıyor
(CLAUDE.md «SIĞMAYAN SEKME KISALTILIR»); mağaza sayfasında kırpık sekme adı istemeyiz.

Boyut değiştirilebilir:  MIKRAPOR_DEMO_BOYUT=1920x1080 python -m demo.calistir
"""

from __future__ import annotations

import os
import sys

VARSAYILAN_BOYUT = (1600, 1000)
ASGARI_STORE = (1366, 768)


def _boyut() -> tuple[int, int]:
    ham = os.environ.get("MIKRAPOR_DEMO_BOYUT", "")
    if "x" in ham.lower():
        try:
            g, y = (int(p) for p in ham.lower().split("x", 1))
        except ValueError:
            return VARSAYILAN_BOYUT
        if g < ASGARI_STORE[0] or y < ASGARI_STORE[1]:
            print(f"UYARI: {g}x{y} Store asgarisi {ASGARI_STORE[0]}x{ASGARI_STORE[1]} altında; "
                  "bu boyutta çekilen ekran görüntüsü reddedilir.", file=sys.stderr)
        return g, y
    return VARSAYILAN_BOYUT


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    import ui.app as app_mod
    from demo.baglayici import demo_moduna_gec

    demo_moduna_gec()

    genislik, yukseklik = _boyut()

    def _demo_ac(window, *, oran: float = 0.80) -> None:
        """Ekran görüntüsü için sabit ve yeterince büyük pencere."""
        window.resize(genislik, yukseklik)
        ekran = QApplication.primaryScreen()
        if ekran is not None:
            geo = ekran.availableGeometry()
            window.move(geo.x() + max(0, (geo.width() - genislik) // 2),
                        geo.y() + max(0, (geo.height() - yukseklik) // 2))
        window.show()

    app_mod._ekrani_orantili_ac = _demo_ac  # noqa: SLF001
    return app_mod.main()


if __name__ == "__main__":
    sys.exit(main())
