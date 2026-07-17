"""Small shared helpers."""
from __future__ import annotations

import os
import re


def sanitize_filename(name: str, max_len: int = 180) -> str:
    """Strip characters unsafe for Windows filenames."""
    if not name:
        return "download"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if not name:
        return "download"
    return name[:max_len]


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def human_bytes(n: float | int | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} PB"


def is_http_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")
