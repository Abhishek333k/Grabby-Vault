"""
Subprocess-based yt-dlp runner for hard cancel/pause (production).

Progress is parsed from yt-dlp --newline stderr lines.
Kill terminates the OS process — more reliable than progress-hook-only abort.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from typing import Callable

from core.logging_setup import get_logger
from core.paths import ffmpeg_location_for_ytdlp

log = get_logger("grabbyvault.download_process")

_PCT = re.compile(r"(\d+(?:\.\d+)?)%")
_SPEED = re.compile(r"at\s+([0-9.]+[KMG]?i?B/s)", re.I)


class ProcessDownloadRunner:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def kill(self):
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
        """
        Returns last known output path (best effort).
        Raises RuntimeError with cancelled/paused/failed message.
        """
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
        ]
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])
        if http_headers:
            # pass common headers
            ua = http_headers.get("user-agent") or http_headers.get("User-Agent")
            ref = http_headers.get("referer") or http_headers.get("Referer")
            if ua:
                cmd.extend(["--user-agent", ua])
            if ref:
                cmd.extend(["--referer", ref])
            cookie = http_headers.get("cookie") or http_headers.get("Cookie")
            if cookie:
                # yt-dlp accepts --add-header
                cmd.extend(["--add-header", f"Cookie:{cookie}"])

        cmd.append(url)

        env = os.environ.copy()
        if ffmpeg_loc:
            env["PATH"] = ffmpeg_loc + os.pathsep + env.get("PATH", "")

        log.info("Spawn yt-dlp process for %s", url[:80])
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

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

                # Destination / merging lines often include path
                if "Destination:" in line:
                    last_file = line.split("Destination:", 1)[-1].strip()
                if "[Merger] Merging formats into" in line:
                    m = re.search(r"into \"(.+)\"", line)
                    if m:
                        last_file = m.group(1)
                if line.startswith("[download]") and progress_callback:
                    pct = 0.0
                    m = _PCT.search(line)
                    if m:
                        pct = float(m.group(1)) / 100.0
                    speed = None
                    sm = _SPEED.search(line)
                    if sm:
                        # leave raw; UI expects bytes/sec ideally
                        speed = None
                    progress_callback(
                        {
                            "status": "downloading",
                            "downloaded_bytes": 0,
                            "total_bytes": 0,
                            "total_bytes_estimate": 0,
                            "_percent_str": f"{pct*100:.1f}%",
                            "speed": speed,
                            "_line": line,
                            # approximate for UI when only percent known
                            "downloaded_bytes": int(pct * 1_000_000),
                            "total_bytes": 1_000_000 if pct else 0,
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
            if rc != 0:
                raise RuntimeError(f"yt-dlp exited with code {rc}")
            if last_file and os.path.isfile(last_file):
                if progress_callback:
                    progress_callback(
                        {"status": "finished", "filename": last_file}
                    )
                return last_file
            return last_file
        finally:
            with self._lock:
                self._proc = None
