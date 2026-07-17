"""Load SilenVault / GrabbyVault brand images for window and tray."""
from __future__ import annotations

import os
from functools import lru_cache

from PIL import Image

from core.paths import app_root, resource_path


def _candidates() -> list[str]:
    root = app_root()
    names = [
        "SILENVAULT CREST.png",
        "SILENVAULT_LOGO.png",
        "BANNER.png",
        "Banner with CREST.png",
        "SILENVAULT CREST.webp",
        "SILENVAULT_LOGO.webp",
        "BANNER.webp",
    ]
    paths = []
    for n in names:
        paths.append(os.path.join(root, "assets", n))
        paths.append(resource_path("assets", n))
    return paths


@lru_cache(maxsize=1)
def brand_image_path() -> str | None:
    for p in _candidates():
        if p and os.path.isfile(p):
            return p
    return None


def load_brand_image(size: tuple[int, int] | None = None) -> Image.Image:
    """Return RGBA image; generated fallback if assets missing."""
    path = brand_image_path()
    if path:
        img = Image.open(path).convert("RGBA")
        if size:
            img = img.copy()
            img.thumbnail(size, Image.Resampling.LANCZOS)
            # Center on square canvas
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            x = (size[0] - img.width) // 2
            y = (size[1] - img.height) // 2
            canvas.paste(img, (x, y), img)
            return canvas
        return img
    # Fallback drawn icon
    from PIL import ImageDraw

    s = size or (64, 64)
    image = Image.new("RGBA", s, (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    m = max(2, s[0] // 16)
    dc.rounded_rectangle(
        [m, m, s[0] - m, s[1] - m],
        radius=s[0] // 6,
        outline=(0, 240, 255, 255),
        width=max(2, s[0] // 20),
        fill=(15, 15, 18, 220),
    )
    return image


def ensure_app_ico(out_name: str = "grabbyvault.ico") -> str | None:
    """Write multi-size .ico under assets/ for Tk / installers. Returns path."""
    root = app_root()
    assets = os.path.join(root, "assets")
    os.makedirs(assets, exist_ok=True)
    ico_path = os.path.join(assets, out_name)
    try:
        base = load_brand_image((256, 256))
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icons = [base.resize(s, Image.Resampling.LANCZOS) for s in sizes]
        icons[0].save(
            ico_path,
            format="ICO",
            sizes=[(i.width, i.height) for i in icons],
            append_images=icons[1:],
        )
        return ico_path if os.path.isfile(ico_path) else None
    except Exception:
        return ico_path if os.path.isfile(ico_path) else None
