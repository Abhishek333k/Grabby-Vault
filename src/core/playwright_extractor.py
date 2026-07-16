import json
from playwright.sync_api import sync_playwright
import time
import urllib.parse
import re

class PlaywrightExtractor:
    """
    A fallback extractor that uses a headless browser to intercept
    media streams (m3u8, mp4) and iframes for sites that defeat yt-dlp.
    """
    
    # Known streaming domains to look out for in iframes
    KNOWN_IFRAME_DOMAINS = [
        'vidplay', 'mycloud', 'megacloud', 'rabbitstream', 
        'vimeo', 'dood', 'streamtape', 'mp4upload', 'filemoon'
    ]

    @staticmethod
    def extract_streams(url: str, timeout_seconds=15) -> dict:
        """
        Loads the page, intercepts network requests for media streams,
        and extracts iframes. Returns a dict formatted similarly to yt-dlp's info dict.
        """
        streams = []
        iframes = []
        
        with sync_playwright() as p:
            # Use Chromium, headless=False to allow user interaction if needed for captchas/play buttons
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            
            print(f"[Playwright] Launching headless browser for {url}...")
            # Apply stealth to avoid Cloudflare bot blocking
            try:
                from playwright_stealth import Stealth
                Stealth().apply_stealth_sync(page)
                print("[Playwright] Applied stealth bypass.")
            except ImportError:
                print("[Playwright] playwright-stealth not installed. Cloudflare may block extraction.")

            # Intercept network requests
            def handle_request(request):
                req_url = request.url
                # Look for master playlists or direct mp4s
                if '.m3u8' in req_url or '.mp4' in req_url:
                    # Ignore small segments or ts files if possible, though .m3u8 is usually what we want
                    if 'master' in req_url or 'index' in req_url or 'playlist' in req_url or '.m3u8' in req_url:
                        # Avoid duplicates
                        if not any(s['url'] == req_url for s in streams):
                            streams.append({
                                'url': req_url,
                                'type': 'm3u8' if '.m3u8' in req_url else 'mp4',
                                'desc': f"Intercepted {'M3U8' if '.m3u8' in req_url else 'MP4'} stream",
                                'http_headers': request.headers
                            })

            page.on("request", handle_request)
            
            cookie_str = None

            try:
                # Go to the page and wait for it to load
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                
                # Wait for up to 60 seconds for the user to interact or the page to load
                print("[Playwright] Waiting for media streams... You may interact with the browser if a CAPTCHA or Play button appears.")
                for i in range(30):
                    if len(streams) > 0:
                        print("[Playwright] Media stream intercepted successfully!")
                        break
                    
                    if i % 5 == 0 and i > 0: # Every 10 seconds try clicking a play button if present
                        # Try clicking generic play buttons after a short wait
                        try:
                            play_buttons = page.locator("#player, .player-container, .play-btn, [id*='player']").locator("button, [class*='play'], svg")
                            if play_buttons.count() > 0:
                                print("[Playwright] Found play button, clicking to trigger stream...")
                                play_buttons.first.click(timeout=2000, force=True)
                        except Exception:
                            pass
                            
                    page.wait_for_timeout(2000)

                # Extract iframes as fallback
                frame_elements = page.locator("iframe").all()
                for frame in frame_elements:
                    src = frame.get_attribute("src")
                    if src:
                        # Normalize protocol-relative URLs
                        if src.startswith("//"):
                            src = "https:" + src
                        elif src.startswith("/"):
                            parsed_url = urllib.parse.urlparse(url)
                            src = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"
                            
                        # Check if it matches known domains
                        is_known = any(domain in src.lower() for domain in PlaywrightExtractor.KNOWN_IFRAME_DOMAINS)
                        desc = "Known Streaming Iframe" if is_known else "Embedded Iframe"
                        
                        if not any(i['url'] == src for i in iframes):
                            iframes.append({
                                'url': src,
                                'type': 'iframe',
                                'desc': f"{desc}: {urllib.parse.urlparse(src).netloc}",
                                'http_headers': {
                                    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                    'Referer': url
                                }
                            })

                cookies = context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            except Exception as e:
                print(f"[Playwright] Error loading page: {e}")
            finally:
                browser.close()
                
        # Post-process headers
        for s in streams:
            raw_headers = s.get('http_headers', {})
            safe_headers = {}
            for k, v in raw_headers.items():
                k_lower = k.lower()
                if k_lower in ['user-agent', 'referer', 'origin', 'accept', 'accept-language', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform']:
                    safe_headers[k_lower] = v
            if cookie_str:
                safe_headers['cookie'] = cookie_str
            s['http_headers'] = safe_headers

        # Compile the results into a mock yt-dlp info dict format
        # We will represent each found stream/iframe as a "format" or we can
        # represent them as a playlist of options so the UI can prompt the user.
        
        # Since these are entirely different sources, it's better to return them as a "playlist"
        # of entries, so the UI can show them as separate items.
        
        entries = []
        
        for idx, stream in enumerate(streams):
            entries.append({
                'id': f"stream_{idx}",
                'title': stream['desc'],
                'url': stream['url'],
                'ext': 'mp4', # Default to mp4 for yt-dlp downloading purposes
                'webpage_url': url,
                'is_playwright_extracted': True,
                'resolution': 'Unknown (Direct Stream)',
                'http_headers': stream.get('http_headers', {})
            })
            
        for idx, iframe in enumerate(iframes):
            entries.append({
                'id': f"iframe_{idx}",
                'title': iframe['desc'],
                'url': iframe['url'], # yt-dlp can try to extract from this iframe URL
                'ext': 'unknown',
                'webpage_url': iframe['url'],
                'is_playwright_extracted': True,
                'resolution': 'Requires further extraction',
                'http_headers': iframe.get('http_headers', {})
            })
            
        if not entries:
            raise Exception("Playwright extracted no media streams or iframes.")
            
        return {
            '_type': 'playlist',
            'id': 'playwright_extraction',
            'title': 'Alternative Streams Found',
            'entries': entries,
            'extractor': 'playwright'
        }
