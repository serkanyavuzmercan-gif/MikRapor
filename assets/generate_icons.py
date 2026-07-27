"""
Kaynak logodan icon.ico, logo.png ve logo-mark.png üretir.
Kullanım: python assets/generate_icons.py [kaynak_png]

Üç çıktı, TEK kaynaktan — pencere ile görev çubuğundaki logo farklı olmasın:
  • icon.ico      — pencere/görev çubuğu ikonu (gri plakalı kutu; küçük boyutta okunur)
  • logo.png      — aynı görsel, 512px
  • logo-mark.png — plakası SÖKÜLMÜŞ hâli; beyaz başlık çubuğunda ve PDF antetinde
                    gri kutu gibi durmasın diye. Çizim ve renkler birebir aynıdır.
"""

from __future__ import annotations

import colorsys
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ASSETS = Path(__file__).resolve().parent
DEFAULT_SOURCE = ASSETS / "logo_source.png"
OUTPUT_PNG = ASSETS / "logo.png"
OUTPUT_ICO = ASSETS / "icon.ico"
OUTPUT_MARK = ASSETS / "logo-mark.png"
CANVAS_SIZE = 512
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _remove_light_background(img: Image.Image, threshold: int = 235) -> Image.Image:
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.int16)
    light = (rgb[:, :, 0] >= threshold) & (rgb[:, :, 1] >= threshold) & (rgb[:, :, 2] >= threshold)
    arr[light, 3] = 0
    return Image.fromarray(arr, mode="RGBA")


def _crop_to_content(img: Image.Image, padding: int = 8) -> Image.Image:
    arr = np.array(img)
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0:
        return img
    left = max(int(xs.min()) - padding, 0)
    top = max(int(ys.min()) - padding, 0)
    right = min(int(xs.max()) + padding + 1, img.width)
    bottom = min(int(ys.max()) + padding + 1, img.height)
    return img.crop((left, top, right, bottom))


# Kaynak logo mor-mavi; uygulama paleti teal. Programın renkleri korunup LOGO uyarlanır.
# Ton aralıkları kaynaktaki iki renk ailesini ayırır: «M» harfi mor (~250-300°), yükselen
# grafik mavi (~185-247°). Hedefler ui/styles.py'den: ACCENT_HOVER ve açık teal.
_BOYAMA: tuple[tuple[tuple[int, int], str], ...] = (
    ((248, 300), "#0d9488"),   # M harfi  → teal (düğme rengi)
    ((185, 247), "#ccfbf1"),   # grafik   → açık teal (hover tonu)
)


def _recolor(img: Image.Image) -> Image.Image:
    """
    Logoyu uygulama paletine boyar; çizimi ve gradyanı bozmadan.

    Ton (H) hedefe sabitlenir; doygunluk ve parlaklık pikselin KENDİ değerinin aile
    ortalamasına oranıyla ölçeklenir. Böylece gradyan, gölge ve kenar yumuşatması
    korunur — düz renk basmak logoyu yassı ve tırtıklı gösteriyordu.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba).astype(float)
    rgb, alfa = arr[:, :, :3] / 255.0, arr[:, :, 3]
    boyut = rgb.shape[:2]
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in rgb.reshape(-1, 3)]).reshape(*boyut, 3)
    h, s, v = hsv[:, :, 0] * 360, hsv[:, :, 1], hsv[:, :, 2]
    gorunur = alfa > 20

    for (h1, h2), hedef in _BOYAMA:
        hr, hg, hb = (int(hedef[i:i + 2], 16) / 255 for i in (1, 3, 5))
        th, ts, tv = colorsys.rgb_to_hsv(hr, hg, hb)
        maske = gorunur & (h >= h1) & (h <= h2) & (s > 0.18)
        if not maske.any():
            continue
        hsv[:, :, 0][maske] = th
        hsv[:, :, 1][maske] = np.clip(s[maske] * (ts / max(s[maske].mean(), 1e-6)), 0, 1)
        hsv[:, :, 2][maske] = np.clip(v[maske] * (tv / max(v[maske].mean(), 1e-6)), 0, 1)

    yeni = np.array([colorsys.hsv_to_rgb(*p) for p in hsv.reshape(-1, 3)]).reshape(*boyut, 3)
    return Image.fromarray(
        np.dstack([np.clip(yeni * 255, 0, 255), alfa]).astype(np.uint8), mode="RGBA")


def _remove_plate(img: Image.Image) -> Image.Image:
    """
    Logonun arkasındaki gri yuvarlak plakayı söker.

    Plaka açık ve DOYGUNLUKSUZ (gri); marka çizimi ise doygun. İkisini ayıran ölçüt
    budur — düz parlaklık eşiği çizimin açık tonlarını da yerdi. _recolor'dan SONRA
    çalışır, o yüzden ölçüt boyamadan bağımsızdır.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.int16)
    doygunluk = rgb.max(axis=2) - rgb.min(axis=2)
    plaka = (doygunluk < 40) & (rgb.min(axis=2) > 150)
    arr[plaka, 3] = 0
    return Image.fromarray(arr, mode="RGBA")


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    scale = min(size / img.width, size / img.height)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    offset = ((size - new_w) // 2, (size - new_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def build_logo_assets(source: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Kaynak logo bulunamadı: {source}")

    raw = Image.open(source)
    cleaned = _remove_light_background(raw)
    cleaned = _crop_to_content(cleaned)
    cleaned = ImageEnhance.Sharpness(cleaned).enhance(1.15)
    cleaned = cleaned.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=2))
    cleaned = _recolor(cleaned)
    logo_hd = _fit_square(cleaned, CANVAS_SIZE)
    logo_hd.save(OUTPUT_PNG, format="PNG", optimize=True)

    logo_ico_base = _fit_square(cleaned, 256)
    logo_ico_base.save(
        OUTPUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )

    # Plakasız marka: aynı çizim, beyaz zemine oturacak hâli.
    mark = _crop_to_content(_remove_plate(cleaned), padding=0)
    _fit_square(mark, CANVAS_SIZE).save(OUTPUT_MARK, format="PNG", optimize=True)

    print(f"OK: {OUTPUT_PNG.name} ({CANVAS_SIZE}px), {OUTPUT_ICO.name} "
          f"({len(ICO_SIZES)} boyut), {OUTPUT_MARK.name} (plakasız)")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    build_logo_assets(src)
