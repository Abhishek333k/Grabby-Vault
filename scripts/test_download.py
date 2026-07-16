"""
CLI smoke test for quality pipeline.
Usage (from project root):
  venv\\Scripts\\python scripts\\test_download.py https://youtu.be/aCBO8uFwGNA
"""
from __future__ import annotations

import os
import sys
import json
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

from core.logging_setup import setup_logging
from core.paths import app_root, ffmpeg_path, downloads_dir
from core.config_manager import ConfigManager
from core.downloader import Downloader
from core.license_manager import LicenseManager
from core.formats import resolve_preset


def main():
    setup_logging()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    url = args[0] if len(args) > 0 else "https://youtu.be/aCBO8uFwGNA"
    quality = args[1] if len(args) > 1 else "1080"
    # Default: first 45s sample so multi-hour 4K videos stay testable
    use_section = "--full" not in flags
    section_range = (0, 45)  # seconds

    print("=== GrabbyVault download test ===")
    print("root     :", app_root())
    print("ffmpeg   :", ffmpeg_path())
    print("downloads:", ConfigManager().get_download_path())
    lic = LicenseManager()
    print("plan     :", lic.tier_label(), "| key:", lic.license_key or "(none)")
    print("section  :", f"{section_range[0]}-{section_range[1]}s" if use_section else "FULL")

    # Ensure pro for quality test unless --free
    if "--free" not in flags:
        if not lic.is_pro:
            print("Activating dev Pro for test...")
            lic.activate("GV-PRO-DEV-UNLOCK")

    dl = Downloader()
    health = dl.health_check()
    print("health   :", json.dumps(health, indent=2))

    print("\nFetching info...")
    info = dl.fetch_info(url, status_callback=lambda m: print(" ", m))
    title = info.get("title", "?")
    print(f"title    : {title}")
    print(f"id       : {info.get('id')}")
    print(f"duration : {info.get('duration')}s")

    preset = resolve_preset(quality)
    print(f"\nDownloading with preset {preset['id']} → {preset['format'][:60]}...")

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                pct = 100.0 * done / total
                spd = d.get("_speed_str") or ""
                print(f"\r  {pct:5.1f}%  {spd}   ", end="", flush=True)
        elif d.get("status") == "finished":
            print("\n  fragment done, post-processing...")

    # Monkey-patch one-shot section via ydl opts by temporary method wrap
    orig = dl.download_video

    def download_with_section(url, format_str=None, progress_callback=None, metadata=None):
        dl._rebuild_base_opts()
        from core.formats import resolve_preset as rp, DEFAULT_FORMAT_SORT, DEFAULT_PRESET_ID
        import yt_dlp
        from core.paths import ffmpeg_location_for_ytdlp

        preset_local = rp(format_str or DEFAULT_PRESET_ID)
        dl._ensure_ffmpeg_for_merge(audio_only=preset_local.get("audio_only", False))
        opts = dl.ydl_opts.copy()
        opts["progress_hooks"] = [progress_callback] if progress_callback else []
        opts["format"] = preset_local["format"]
        opts["format_sort"] = DEFAULT_FORMAT_SORT
        if preset_local.get("merge"):
            opts["merge_output_format"] = preset_local["merge"]
        if use_section:
            # Sample clip for long videos (requires ffmpeg). ranges = [(start, end)] seconds
            opts["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [section_range]
            )
            opts["force_keyframes_at_cuts"] = True
            base = ConfigManager().get_download_path()
            opts["outtmpl"] = os.path.join(
                base, "test_samples", "%(title).120B.%(ext)s"
            )
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    download_with_section(url, format_str=quality, progress_callback=hook)
    print("\nDownload finished.")

    # Probe newest media file (prefer test_samples/)
    out = ConfigManager().get_download_path()
    media = []
    for root, _dirs, files in os.walk(out):
        for name in files:
            if name.lower().endswith((".mp4", ".mkv", ".webm", ".m4a", ".mp3")):
                p = os.path.join(root, name)
                media.append((os.path.getmtime(p), p))
    if not media:
        print("No media file found in downloads/")
        return 1
    media.sort(reverse=True)
    latest = media[0][1]
    print("file     :", latest)
    print("size_mb  :", round(os.path.getsize(latest) / 1e6, 2))

    ffprobe = os.path.join(app_root(), "bin", "ffprobe.exe")
    if os.path.isfile(ffprobe):
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,bit_rate",
            "-of",
            "json",
            latest,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print("ffprobe  :", r.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
