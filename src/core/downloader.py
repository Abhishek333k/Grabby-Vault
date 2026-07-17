import os
import shutil
import urllib.request
from PIL import Image
import io
import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from core.config_manager import ConfigManager
from core.formats import (
    DEFAULT_FORMAT_SORT,
    DEFAULT_PRESET_ID,
    LEGACY_DEFAULT_FORMAT,
    resolve_preset,
)
from core.paths import app_root, ffmpeg_location_for_ytdlp, ffmpeg_path
from core.logging_setup import get_logger

log = get_logger("grabbyvault.downloader")


class DownloadAborted(Exception):
    """Raised when user cancels or pauses an active download."""

    def __init__(self, reason: str = "cancelled"):
        self.reason = reason  # 'cancelled' | 'paused'
        super().__init__(
            "Download cancelled by user"
            if reason == "cancelled"
            else "Download paused by user"
        )


def _detect_js_runtimes() -> dict:
    runtimes = {}
    for name in ("node", "deno", "bun"):
        path = shutil.which(name)
        if path:
            runtimes[name] = {"path": path}
    return runtimes


class Downloader:
    def __init__(self):
        self.config = ConfigManager()
        self._rebuild_base_opts()

    def _rebuild_base_opts(self):
        download_path = self.config.get_download_path()
        os.makedirs(download_path, exist_ok=True)
        outtmpl = os.path.join(download_path, "%(title).200B.%(ext)s")

        ff_exe = ffmpeg_path()
        self._ffmpeg_ok = ff_exe is not None
        ffmpeg_loc = ffmpeg_location_for_ytdlp() or (
            os.path.dirname(ff_exe) if ff_exe else None
        )

        self.ydl_opts = {
            "outtmpl": outtmpl,
            "format": LEGACY_DEFAULT_FORMAT,
            "format_sort": DEFAULT_FORMAT_SORT,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "writethumbnail": bool(self.config.get("embed_thumbnail", True)),
            "writesubtitles": bool(self.config.get("write_subtitles", True)),
            "writeautomaticsub": False,
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "postprocessors": [
                {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
            ],
            "quiet": True,
            "no_warnings": True,
            "retries": 10,
            "fragment_retries": 10,
            "concurrent_fragment_downloads": 4,
            "ignoreerrors": False,
            "impersonate": ImpersonateTarget(client="chrome"),
        }
        if ffmpeg_loc:
            self.ydl_opts["ffmpeg_location"] = ffmpeg_loc
        if ffmpeg_loc and ffmpeg_loc not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_loc + os.pathsep + os.environ.get("PATH", "")

        js = _detect_js_runtimes()
        if js:
            self.ydl_opts["js_runtimes"] = js
            log.debug("JS runtimes for yt-dlp: %s", list(js.keys()))
        else:
            log.warning(
                "No JS runtime (node/deno) found — YouTube formats may be limited."
            )

    def _ensure_ffmpeg_for_merge(self, audio_only: bool = False):
        if self._ffmpeg_ok:
            return
        if audio_only:
            raise Exception(
                "ffmpeg not found in bin/. Required for audio conversion (MP3/M4A)."
            )
        raise Exception(
            "ffmpeg not found in bin/. Required to merge video+audio "
            "(without it you often get low quality or silent files)."
        )

    def health_check(self) -> dict:
        self._rebuild_base_opts()
        return {
            "ffmpeg_ok": self._ffmpeg_ok,
            "ffmpeg_path": ffmpeg_path(),
            "ffmpeg_location": self.ydl_opts.get("ffmpeg_location"),
            "js_runtimes": list(_detect_js_runtimes().keys()),
            "download_path": self.config.get_download_path(),
            "app_root": app_root(),
            "yt_dlp_version": getattr(yt_dlp.version, "__version__", "unknown"),
        }

    def fetch_info(self, url: str, status_callback=None):
        self._rebuild_base_opts()
        opts = self.ydl_opts.copy()
        opts["writethumbnail"] = False
        opts["writesubtitles"] = False
        opts["extract_flat"] = "in_playlist"
        opts.pop("postprocessors", None)

        fallbacks = [
            {"desc": "Standard (Chrome Impersonation)", "opts": {}},
            {
                "desc": "Safari Impersonation",
                "opts": {"impersonate": ImpersonateTarget(client="safari")},
            },
            {"desc": "No Impersonation (Default)", "opts": {"impersonate": None}},
            {
                "desc": "Cookies from Firefox",
                "opts": {"cookiesfrombrowser": ("firefox",)},
            },
            {"desc": "Cookies from Edge", "opts": {"cookiesfrombrowser": ("edge",)}},
            {
                "desc": "Cookies from Chrome",
                "opts": {"cookiesfrombrowser": ("chrome",)},
            },
        ]

        errors = []
        for attempt in fallbacks:
            if status_callback:
                status_callback(f"Trying {attempt['desc']}...")

            current_opts = opts.copy()
            current_opts.update(attempt["opts"])

            try:
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        return info
            except Exception as e:
                err_str = str(e)
                log.warning(
                    "fetch_info attempt failed (%s): %s", attempt["desc"], err_str
                )
                if "Unsupported URL" in err_str:
                    errors.append("Unsupported URL")
                    break
                errors.append(err_str)
                continue

        if "Unsupported URL" in errors:
            if status_callback:
                status_callback("Trying Advanced Browser Extraction...")
            try:
                from core.playwright_extractor import PlaywrightExtractor

                headless = bool(self.config.get("playwright_headless", False))
                timeout = int(self.config.get("playwright_timeout_seconds", 45) or 45)
                info = PlaywrightExtractor.extract_streams(
                    url, timeout_seconds=timeout, headless=headless
                )
                if info:
                    return info
            except Exception as pe:
                raise Exception(
                    f"Unsupported URL and Advanced Extraction Failed: {pe}"
                ) from pe

        last_err = errors[-1] if errors else "Unknown Error"
        if "DPAPI" in last_err:
            raise Exception(
                "Browser Cookies Encrypted (DPAPI). Please use a supported URL "
                "or an external cookies.txt file."
            )
        raise Exception(f"All extraction methods failed. Last error: {last_err}")

    def download_video(
        self,
        url: str,
        format_str: str = None,
        progress_callback=None,
        metadata=None,
        abort_check=None,
    ) -> str | None:
        """
        Download and return final filepath if known.
        abort_check: callable () -> 'cancelled'|'paused'|None
        """
        self._rebuild_base_opts()
        last_filepath = {"path": None}

        def _hook(d):
            if abort_check:
                reason = abort_check()
                if reason in ("cancelled", "paused"):
                    raise DownloadAborted(reason)
            status = d.get("status")
            if status == "finished":
                fn = d.get("filename")
                if fn:
                    last_filepath["path"] = fn
            if progress_callback:
                progress_callback(d)

        preset = resolve_preset(format_str or DEFAULT_PRESET_ID)
        self._ensure_ffmpeg_for_merge(audio_only=preset.get("audio_only", False))

        opts = self.ydl_opts.copy()
        opts["progress_hooks"] = [_hook]
        opts["format"] = preset["format"]
        opts["format_sort"] = DEFAULT_FORMAT_SORT

        if preset.get("merge"):
            opts["merge_output_format"] = preset["merge"]

        if preset.get("audio_only"):
            opts["writethumbnail"] = False
            opts["writesubtitles"] = False
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": preset.get("audio_codec", "mp3"),
                    "preferredquality": preset.get("audio_quality", "192"),
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]

        if metadata and metadata.get("playlist_title"):
            safe_title = "".join(
                c
                for c in metadata["playlist_title"]
                if c.isalpha() or c.isdigit() or c in " -_"
            ).strip()
            if safe_title:
                download_path = self.config.get_download_path()
                opts["outtmpl"] = os.path.join(
                    download_path, safe_title, "%(title).200B.%(ext)s"
                )

        if metadata and "http_headers" in metadata:
            opts["http_headers"] = metadata["http_headers"]
            referer = metadata["http_headers"].get("Referer") or metadata[
                "http_headers"
            ].get("referer")
            if referer:
                opts["referer"] = referer

        if url and (".m3u8" in url.lower() or "master" in url.lower()):
            if not format_str or format_str in ("best", "bestaudio/best"):
                opts["format"] = LEGACY_DEFAULT_FORMAT
            opts["format_sort"] = ["res", "br", "tbr", "vbr", "abr", "size"]

        log.info(
            "Downloading url=%s format=%s preset=%s",
            url[:80],
            opts.get("format"),
            preset.get("id"),
        )

        use_proc = bool(self.config.get("use_process_download", True))
        # Process runner cannot easily do audio extract postprocessors — use in-process
        if use_proc and not preset.get("audio_only"):
            from core.download_process import ProcessDownloadRunner

            runner = ProcessDownloadRunner()
            # Stash for emergency kill if needed
            self._active_runner = runner
            try:
                if abort_check and abort_check() in ("cancelled", "paused"):
                    raise DownloadAborted(abort_check())
                path = runner.run(
                    url,
                    format_str=opts["format"],
                    outtmpl=opts["outtmpl"],
                    merge_format=opts.get("merge_output_format") or "mp4",
                    http_headers=opts.get("http_headers"),
                    progress_callback=progress_callback,
                    abort_check=abort_check,
                )
                last_filepath["path"] = path
            except RuntimeError as e:
                msg = str(e)
                if "cancelled by user" in msg.lower():
                    raise DownloadAborted("cancelled") from e
                if "paused by user" in msg.lower():
                    raise DownloadAborted("paused") from e
                raise
            finally:
                self._active_runner = None
        else:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if abort_check and abort_check() in ("cancelled", "paused"):
                    raise DownloadAborted(abort_check())
                info = ydl.extract_info(url, download=True)
                if info and not last_filepath["path"]:
                    try:
                        last_filepath["path"] = ydl.prepare_filename(info)
                    except Exception:
                        pass
                if info and info.get("requested_downloads"):
                    for rd in info["requested_downloads"]:
                        fp = rd.get("filepath")
                        if fp and os.path.isfile(fp):
                            last_filepath["path"] = fp
                elif info and info.get("_filename") and os.path.isfile(
                    info["_filename"]
                ):
                    last_filepath["path"] = info["_filename"]

        path = last_filepath["path"]
        if path and not os.path.isfile(path):
            base, _ = os.path.splitext(path)
            for ext in (".mp4", ".mkv", ".webm", ".m4a", ".mp3"):
                cand = base + ext
                if os.path.isfile(cand):
                    path = cand
                    break
        return path if path and os.path.isfile(path) else last_filepath["path"]

    @staticmethod
    def fetch_thumbnail(url: str):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                return Image.open(io.BytesIO(data))
        except Exception as e:
            log.debug("Thumbnail failed %s: %s", url, e)
            return None
