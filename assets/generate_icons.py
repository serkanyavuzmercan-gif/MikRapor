"""
Kaynak logodan icon.ico ve logo.png üretir.
Kullanım: python assets/generate_icons.py [kaynak_png]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ASSETS = Path(__file__).resolve().parent
DEFAULT_SOURCE = ASSETS / "logo_source.png"
OUTPUT_PNG = ASSETS / "logo.png"
OUTPUT_ICO = ASSETS / "icon.ico"
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
    logo_hd = _fit_square(cleaned, CANVAS_SIZE)
    logo_hd.save(OUTPUT_PNG, format="PNG", optimize=True)

    logo_ico_base = _fit_square(cleaned, 256)
    logo_ico_base.save(
        OUTPUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )
    print(f"OK: {OUTPUT_PNG.name} ({CANVAS_SIZE}px), {OUTPUT_ICO.name} ({len(ICO_SIZES)} boyut)")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    build_logo_assets(src)
