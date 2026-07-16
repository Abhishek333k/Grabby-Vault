"""
Portable path helpers for GrabbyVault.

Resolves app root whether launched via:
  - python src/main.py
  - run.bat from project root
  - frozen PyInstaller exe
"""
from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def app_root() -> str:
    """Install / project directory (bin/, config.json, downloads/)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))

    # src/core/paths.py -> project root
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.abspath(os.path.join(here, "..", ".."))
    markers = ("bin", "config.json", "requirements.txt", "src")
    if any(
        os.path.exists(os.path.join(candidate, m)) for m in markers
    ):
        return candidate

    cwd = os.path.abspath(os.getcwd())
    if any(os.path.exists(os.path.join(cwd, m)) for m in markers):
        return cwd
    return candidate


def resource_path(*parts: str) -> str:
    """Path inside the app root (or MEIPASS for bundled data)."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
        p = os.path.join(base, *parts)
        if os.path.exists(p):
            return p
    return os.path.join(app_root(), *parts)


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def downloads_dir(configured: str | None = None) -> str:
    if configured and configured.strip():
        p = configured.strip()
        if not os.path.isabs(p):
            p = os.path.join(app_root(), p)
        return ensure_dir(os.path.abspath(p))
    return ensure_dir(os.path.join(app_root(), "downloads"))


def logs_dir() -> str:
    return ensure_dir(os.path.join(app_root(), "logs"))


def bin_dir() -> str:
    return os.path.join(app_root(), "bin")


def config_path() -> str:
    return os.path.join(app_root(), "config.json")


def db_path() -> str:
    return os.path.join(app_root(), "queue.db")


def ffmpeg_path() -> str | None:
    """Return path to ffmpeg executable if found."""
    b = bin_dir()
    for name in ("ffmpeg.exe", "ffmpeg"):
        p = os.path.join(b, name)
        if os.path.isfile(p):
            return p
    # PATH fallback
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        for name in ("ffmpeg.exe", "ffmpeg"):
            p = os.path.join(path_dir, name)
            if os.path.isfile(p):
                return p
    return None


def ffprobe_path() -> str | None:
    b = bin_dir()
    for name in ("ffprobe.exe", "ffprobe"):
        p = os.path.join(b, name)
        if os.path.isfile(p):
            return p
    return None


def ffmpeg_location_for_ytdlp() -> str | None:
    """Directory or binary path yt-dlp accepts for ffmpeg_location."""
    exe = ffmpeg_path()
    if not exe:
        return None
    # Prefer directory containing ffmpeg (yt-dlp docs)
    return os.path.dirname(exe)
