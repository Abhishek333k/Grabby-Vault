from playwright.sync_api import sync_playwright
import urllib.parse


class PlaywrightExtractor:
    """
    Fallback extractor: intercepts m3u8/mp4 and iframes when yt-dlp fails.
    """

    KNOWN_IFRAME_DOMAINS = [
        "vidplay",
        "mycloud",
        "megacloud",
        "rabbitstream",
        "vimeo",
        "dood",
        "streamtape",
        "mp4upload",
        "filemoon",
    ]

    @staticmethod
    def extract_streams(
        url: str, timeout_seconds: int = 45, headless: bool = False
    ) -> dict:
        streams = []
        iframes = []
        cookie_str = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            print(
                f"[Playwright] Launching browser (headless={headless}) for {url}..."
            )
            try:
                from playwright_stealth import Stealth

                Stealth().apply_stealth_sync(page)
                print("[Playwright] Applied stealth bypass.")
            except ImportError:
                print(
                    "[Playwright] playwright-stealth not installed. "
                    "Cloudflare may block extraction."
                )

            def handle_request(request):
                req_url = request.url
                if ".m3u8" in req_url or ".mp4" in req_url:
                    if (
                        "master" in req_url
                        or "index" in req_url
                        or "playlist" in req_url
                        or ".m3u8" in req_url
                    ):
                        if not any(s["url"] == req_url for s in streams):
                            streams.append(
                                {
                                    "url": req_url,
                                    "type": "m3u8" if ".m3u8" in req_url else "mp4",
                                    "desc": (
                                        f"Intercepted "
                                        f"{'M3U8' if '.m3u8' in req_url else 'MP4'} stream"
                                    ),
                                    "http_headers": request.headers,
                                }
                            )

            page.on("request", handle_request)

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=max(5, timeout_seconds) * 1000,
                )

                # Wait up to timeout_seconds for streams (2s steps)
                steps = max(1, timeout_seconds // 2)
                print(
                    "[Playwright] Waiting for media streams... "
                    "Interact with the browser if CAPTCHA/Play appears."
                )
                for i in range(steps):
                    if streams:
                        print("[Playwright] Media stream intercepted successfully!")
                        break

                    if i > 0 and i % 5 == 0:
                        try:
                            play_buttons = page.locator(
                                "#player, .player-container, .play-btn, [id*='player']"
                            ).locator("button, [class*='play'], svg")
                            if play_buttons.count() > 0:
                                print("[Playwright] Clicking play control...")
                                play_buttons.first.click(timeout=2000, force=True)
                        except Exception:
                            pass

                    page.wait_for_timeout(2000)

                frame_elements = page.locator("iframe").all()
                for frame in frame_elements:
                    src = frame.get_attribute("src")
                    if not src:
                        continue
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        parsed_url = urllib.parse.urlparse(url)
                        src = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"

                    is_known = any(
                        domain in src.lower()
                        for domain in PlaywrightExtractor.KNOWN_IFRAME_DOMAINS
                    )
                    desc = (
                        "Known Streaming Iframe"
                        if is_known
                        else "Embedded Iframe"
                    )
                    if not any(i["url"] == src for i in iframes):
                        iframes.append(
                            {
                                "url": src,
                                "type": "iframe",
                                "desc": f"{desc}: {urllib.parse.urlparse(src).netloc}",
                                "http_headers": {
                                    "User-Agent": (
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/120.0.0.0 Safari/537.36"
                                    ),
                                    "Referer": url,
                                },
                            }
                        )

                cookies = context.cookies()
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies
                )
            except Exception as e:
                print(f"[Playwright] Error loading page: {e}")
            finally:
                browser.close()

        for s in streams:
            raw_headers = s.get("http_headers", {})
            safe_headers = {}
            for k, v in raw_headers.items():
                k_lower = k.lower()
                if k_lower in [
                    "user-agent",
                    "referer",
                    "origin",
                    "accept",
                    "accept-language",
                    "sec-ch-ua",
                    "sec-ch-ua-mobile",
                    "sec-ch-ua-platform",
                ]:
                    safe_headers[k_lower] = v
            if cookie_str:
                safe_headers["cookie"] = cookie_str
            s["http_headers"] = safe_headers

        entries = []
        for idx, stream in enumerate(streams):
            entries.append(
                {
                    "id": f"stream_{idx}",
                    "title": stream["desc"],
                    "url": stream["url"],
                    "ext": "mp4",
                    "webpage_url": url,
                    "is_playwright_extracted": True,
                    "resolution": "Unknown (Direct Stream)",
                    "http_headers": stream.get("http_headers", {}),
                }
            )

        for idx, iframe in enumerate(iframes):
            entries.append(
                {
                    "id": f"iframe_{idx}",
                    "title": iframe["desc"],
                    "url": iframe["url"],
                    "ext": "unknown",
                    "webpage_url": iframe["url"],
                    "is_playwright_extracted": True,
                    "resolution": "Requires further extraction",
                    "http_headers": iframe.get("http_headers", {}),
                }
            )

        if not entries:
            raise Exception("Playwright extracted no media streams or iframes.")

        return {
            "_type": "playlist",
            "id": "playwright_extraction",
            "title": "Alternative Streams Found",
            "entries": entries,
            "extractor": "playwright",
        }
