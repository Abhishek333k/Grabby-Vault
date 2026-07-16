import re

class URLRouter:
    @staticmethod
    def get_platform(url: str) -> str:
        url = url.lower()
        if re.search(r'(youtube\.com|youtu\.be)', url):
            return "YouTube"
        elif "dailymotion.com" in url or "dai.ly" in url:
            return "Dailymotion"
        elif "instagram.com" in url:
            return "Instagram"
        elif "tiktok.com" in url:
            return "TikTok"
        elif "facebook.com" in url or "fb.watch" in url:
            return "Facebook"
        elif "vimeo.com" in url:
            return "Vimeo"
        elif "aniwave" in url or "hianime" in url:
            return "AniWave / HiAnime"
        elif "twitter.com" in url or "x.com" in url:
            return "X/Twitter"
        elif "twitch.tv" in url:
            return "Twitch"
        elif "reddit.com" in url:
            return "Reddit"
        else:
            return "Unknown"
