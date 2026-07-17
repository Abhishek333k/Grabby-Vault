"""
Subprocess-based yt-dlp runner for hard cancel/pause.

Progress parsed from yt-dlp --newline output.
A watchdog thread kills the process if abort is set during silent stalls.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Callable

from core.logging_setup import get_logger
from core.paths import ffmpeg_location_for_ytdlp

log = get_logger("grabbyvault.download_process")

_PCT = re.compile(r"(\d+(?:\.\d+)?)%")
_SPEED = re.compile(r"at\s+([\d.]+)\s*([KMG]i?B)/s", re.I)
_ETA = re.compile(r"ETA\s+(\d+:\d+(?::\d+)?)", re.I)


def _speed_to_bps(value: float, unit: str) -> float:
    u = unit.upper().replace("I", "")
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}.get(u, 1)
    return value * mult


class ProcessDownloadRunner:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._kill_requested = False

    def kill(self):
        self._kill_requested = True
        with self._lock:
            proc = self._proc
        if not proc or proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except Exception as e:
            log.warning("kill download process: %s", e)

    def run(
        self,
        url: str,
        *,
        format_str: str,
        outtmpl: str,
        merge_format: str = "mp4",
        http_headers: dict | None = None,
        progress_callback: Callable | None = None,
        abort_check: Callable | None = None,
    ) -> str | None:
        ffmpeg_loc = ffmpeg_location_for_ytdlp()
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--newline",
            "--no-playlist",
            "-f",
            format_str,
            "-o",
            outtmpl,
            "--merge-output-format",
            merge_format,
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--concurrent-fragments",
            "4",
        ]
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])
        if http_headers:
            ua = http_headers.get("user-agent") or http_headers.get("User-Agent")
            ref = http_headers.get("referer") or http_headers.get("Referer")
            if ua:
                cmd.extend(["--user-agent", ua])
            if ref:
                cmd.extend(["--referer", ref])
            cookie = http_headers.get("cookie") or http_headers.get("Cookie")
            if cookie:
                cmd.extend(["--add-header", f"Cookie:{cookie}"])

        cmd.append(url)

        env = os.environ.copy()
        if ffmpeg_loc:
            env["PATH"] = ffmpeg_loc + os.pathsep + env.get("PATH", "")

        log.info("Spawn yt-dlp process for %s", url[:80])
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        self._kill_requested = False
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creationflags,
        )
        with self._lock:
            self._proc = proc

        stop_watch = threading.Event()

        def _watchdog():
            while not stop_watch.wait(0.4):
                if not abort_check:
                    continue
                reason = abort_check()
                if reason in ("cancelled", "paused") or self._kill_requested:
                    self.kill()
                    return

        wd = threading.Thread(target=_watchdog, daemon=True, name="dl-watchdog")
        wd.start()

        last_file = None
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                if abort_check:
                    reason = abort_check()
                    if reason in ("cancelled", "paused"):
                        self.kill()
                        raise RuntimeError(
                            "Download cancelled by user"
                            if reason == "cancelled"
                            else "Download paused by user"
                        )

                if "Destination:" in line:
                    last_file = line.split("Destination:", 1)[-1].strip().strip('"')
                if "[Merger] Merging formats into" in line:
                    m = re.search(r'into ["\'](.+?)["\']', line)
                    if m:
                        last_file = m.group(1)
                if "[ExtractAudio]" in line and "Destination:" in line:
                    last_file = line.split("Destination:", 1)[-1].strip().strip('"')

                if progress_callback and (
                    line.startswith("[download]") or "ETA" in line
                ):
                    pct = 0.0
                    m = _PCT.search(line)
                    if m:
                        pct = min(1.0, float(m.group(1)) / 100.0)
                    speed = None
                    sm = _SPEED.search(line)
                    if sm:
                        try:
                            speed = _speed_to_bps(float(sm.group(1)), sm.group(2))
                        except ValueError:
                            speed = None
                    progress_callback(
                        {
                            "status": "downloading",
                            "downloaded_bytes": int(pct * 1_000_000) if pct else 0,
                            "total_bytes": 1_000_000 if pct else 0,
                            "total_bytes_estimate": 1_000_000 if pct else 0,
                            "speed": speed,
                            "_percent": pct,
                            "_line": line,
                        }
                    )

            rc = proc.wait()
            if abort_check and abort_check() in ("cancelled", "paused"):
                reason = abort_check()
                raise RuntimeError(
                    "Download cancelled by user"
                    if reason == "cancelled"
                    else "Download paused by user"
                )
            if self._kill_requested:
                raise RuntimeError("Download cancelled by user")
            if rc != 0:
                raise RuntimeError(f"yt-dlp exited with code {rc}")
            if last_file and os.path.isfile(last_file):
                if progress_callback:
                    progress_callback({"status": "finished", "filename": last_file})
                return last_file
            return last_file
        finally:
            stop_watch.set()
            with self._lock:
                self._proc = None
