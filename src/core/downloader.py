import yt_dlp
import os
import urllib.request
from PIL import Image
import io
from core.config_manager import ConfigManager
from yt_dlp.networking.impersonate import ImpersonateTarget

class Downloader:
    """
    Core engine wrapper for yt-dlp to handle video downloading operations.
    """
    def __init__(self):
        config = ConfigManager()
        download_path = config.get("download_path", os.path.abspath('downloads'))
        os.makedirs(download_path, exist_ok=True)
        outtmpl = os.path.join(download_path, '%(title)s.%(ext)s')

        self.ydl_opts = {
            'ffmpeg_location': os.path.abspath('bin'),
            'outtmpl': outtmpl,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mkv',
            'noplaylist': True,
            'writethumbnail': True,
            'writesubtitles': True,
            'subtitleslangs': ['en'],
            'postprocessors': [
                {'key': 'FFmpegEmbedSubtitle'},
                {'key': 'FFmpegMetadata'},
            ],
            # Avoid printing output to terminal by default
            'quiet': True,
            'no_warnings': True,
            'impersonate': ImpersonateTarget(client='chrome'), # crucial for AniWaves / HiAnime
        }

    def fetch_info(self, url: str, status_callback=None):
        """
        Fetches metadata for a given URL without downloading.
        For playlists, it extracts the flat list.
        Includes fallback logic for tricky sites.
        """
        opts = self.ydl_opts.copy()
        # Don't try to write anything during info fetching
        opts['writethumbnail'] = False
        opts['writesubtitles'] = False
        opts['extract_flat'] = True  # crucial for fast playlist extraction
        
        fallbacks = [
            {"desc": "Standard (Chrome Impersonation)", "opts": {}},
            {"desc": "Safari Impersonation", "opts": {"impersonate": ImpersonateTarget(client='safari')}},
            {"desc": "No Impersonation (Default)", "opts": {"impersonate": None}},
            {"desc": "Cookies from Firefox", "opts": {"cookiesfrombrowser": ("firefox",)}},
            {"desc": "Cookies from Edge", "opts": {"cookiesfrombrowser": ("edge",)}},
            {"desc": "Cookies from Chrome", "opts": {"cookiesfrombrowser": ("chrome",)}}
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
                if "Unsupported URL" in err_str:
                    errors.append(f"Unsupported URL")
                    break # No point in trying other fallbacks if the URL itself is fundamentally unsupported by any extractor
                errors.append(err_str)
                continue
                
        # If we broke out early due to unsupported URL, try Playwright Extractor
        if "Unsupported URL" in errors:
            if status_callback:
                status_callback("Trying Advanced Browser Extraction...")
            
            try:
                from core.playwright_extractor import PlaywrightExtractor
                info = PlaywrightExtractor.extract_streams(url)
                if info:
                    return info
            except Exception as pe:
                raise Exception(f"Unsupported URL and Advanced Extraction Failed: {pe}")
            
        last_err = errors[-1] if errors else "Unknown Error"
        if "DPAPI" in last_err:
            raise Exception("Browser Cookies Encrypted (DPAPI). Please use a supported URL or an external cookies.txt file.")
            
        raise Exception(f"All extraction methods failed. Last error: {last_err}")

    def download_video(self, url: str, format_str: str = None, progress_callback=None, metadata=None):
        """
        Downloads a video synchronously. Should be called from a worker thread.
        """
        def _hook(d):
            if progress_callback:
                progress_callback(d)
                
        # For actual downloading, we should ideally use the same fallback that worked,
        # but for simplicity we will just stick to the default impersonate: chrome.
        # It's usually the extraction that fails, the actual video URL is often fine.
        opts = self.ydl_opts.copy()
        opts['progress_hooks'] = [_hook]
        if format_str:
            opts['format'] = format_str
            
        if metadata and metadata.get('playlist_title'):
            # Create a safe folder name from the playlist title
            safe_title = "".join([c for c in metadata['playlist_title'] if c.isalpha() or c.isdigit() or c in ' -_']).strip()
            if safe_title:
                config = ConfigManager()
                download_path = config.get("download_path", os.path.abspath('downloads'))
                opts['outtmpl'] = os.path.join(download_path, safe_title, '%(title)s.%(ext)s')
            
        if metadata and 'http_headers' in metadata:
            opts['http_headers'] = metadata['http_headers']
            # Sometimes we also need to pass the referer specifically if yt-dlp tries to be smart
            referer = metadata['http_headers'].get('Referer') or metadata['http_headers'].get('referer')
            if referer:
                opts['referer'] = referer
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    @staticmethod
    def fetch_thumbnail(url: str):
        """
        Downloads a thumbnail from a URL and returns a PIL Image.
        Returns None if failed.
        """
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
                img = Image.open(io.BytesIO(data))
                return img
        except Exception as e:
            print(f"Failed to fetch thumbnail {url}: {e}")
            return None
