"""Lighter copies of the captures for the video: 1.3 image px per CSS px (the frame never needs more), as JPEG."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "assets" / "shots"
out = src / "web"
out.mkdir(exist_ok=True)
for png in sorted(src.glob("*.png")):
    with Image.open(png) as im:
        css_w = im.width / 2
        w = round(css_w * 1.3)
        h = round(im.height * w / im.width)
        im.convert("RGB").resize((w, h), Image.LANCZOS).save(out / f"{png.stem}.jpg", quality=88, optimize=True)
    print(png.stem, (w, h), round((out / f"{png.stem}.jpg").stat().st_size / 1e6, 2), "MB")
