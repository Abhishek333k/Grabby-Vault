"""
Free / Pro licensing for GrabbyVault.

Lemon Squeezy integration (production):
  - User buys Pro → receives license key
  - App stores key in config.json
  - Optional online validation against Lemon Squeezy API later

For local testing without a store:
  - Use a dev key: GV-PRO-DEV-UNLOCK
  - Or set "pro_unlocked": true in config.json
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from core.config_manager import ConfigManager
from core.formats import resolve_preset

# Placeholder storefront URLs — replace with your Lemon Squeezy product links
LEMON_SQUEEZY_CHECKOUT_URL = "https://grabbyvault.lemonsqueezy.com/buy/pro"
LEMON_SQUEEZY_DONATE_URL = "https://grabbyvault.lemonsqueezy.com/buy/donate"
# Alternate donate if LS not ready yet
DONATE_FALLBACK_URL = "https://www.buymeacoffee.com/grabbyvault"

# Local dev unlock (documented for you; change before public release if desired)
DEV_PRO_KEYS = {
    "GV-PRO-DEV-UNLOCK",
    "GV-TEST-PRO-0000",
}

# Free tier limits
FREE_MAX_CONCURRENT = 1
FREE_MAX_HEIGHT = 720
PRO_MAX_CONCURRENT = 5

# Presets free users may select
FREE_PRESET_IDS = {"720", "480", "audio_mp3", "audio_m4a"}


class LicenseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.config = ConfigManager()

    def refresh(self):
        self.config = ConfigManager()
        self.config.load_config()  # reloads self.config from disk

    @property
    def license_key(self) -> str:
        return (self.config.get("license_key") or "").strip()

    @property
    def is_pro(self) -> bool:
        if self.config.get("pro_unlocked") is True:
            return True
        key = self.license_key.upper().replace(" ", "")
        if not key:
            return False
        if key in DEV_PRO_KEYS:
            return True
        # Accept GV-XXXX-XXXX-XXXX style keys (checksum stub for offline)
        if self._offline_key_valid(key):
            return True
        return False

    def _offline_key_valid(self, key: str) -> bool:
        """
        Lightweight offline check for keys you will generate later.
        Format: GV-XXXX-XXXX-XXXX where last group is a simple hash nibble of rest.
        Real Lemon Squeezy validation can replace this.
        """
        m = re.fullmatch(r"GV-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})", key)
        if not m:
            return False
        body = f"{m.group(1)}-{m.group(2)}"
        digest = hashlib.sha256(f"GrabbyVault|{body}".encode()).hexdigest()[:4].upper()
        return digest == m.group(3)

    def activate(self, key: str) -> tuple[bool, str]:
        key = (key or "").strip().upper().replace(" ", "")
        if not key:
            return False, "Enter a license key."
        # Temporarily store and re-check
        prev = self.config.get("license_key")
        self.config.set("license_key", key)
        if self.is_pro:
            return True, "Pro activated. Thank you for supporting GrabbyVault!"
        self.config.set("license_key", prev or "")
        return False, "Invalid license key. Check your Lemon Squeezy email or use a test key."

    def deactivate(self):
        self.config.set("license_key", "")
        self.config.set("pro_unlocked", False)

    def tier_label(self) -> str:
        return "PRO" if self.is_pro else "FREE"

    def max_concurrent(self) -> int:
        if self.is_pro:
            return min(
                int(self.config.get("max_concurrent_downloads", PRO_MAX_CONCURRENT)),
                PRO_MAX_CONCURRENT,
            )
        return FREE_MAX_CONCURRENT

    def allowed_presets(self) -> list[dict[str, Any]]:
        from core.formats import QUALITY_PRESETS

        if self.is_pro:
            return list(QUALITY_PRESETS)
        return [p for p in QUALITY_PRESETS if p["id"] in FREE_PRESET_IDS]

    def clamp_format(self, format_str: str | None) -> tuple[str, str | None]:
        """
        Enforce Free tier quality caps.
        Returns (format_or_preset_id, warning_message_or_None).
        """
        preset = resolve_preset(format_str)
        if self.is_pro:
            return preset["id"] if preset["id"] != "custom" else (format_str or "best"), None

        pid = preset.get("id", "720")
        if pid in FREE_PRESET_IDS:
            return pid, None
        if pid in ("best", "2160", "1440", "1080", "custom"):
            return "720", "Free tier is limited to 720p. Upgrade to Pro for 1080p/4K/Best."
        return "720", "Free tier is limited to 720p. Upgrade to Pro for higher quality."

    def checkout_url(self) -> str:
        return self.config.get("lemonsqueezy_checkout_url") or LEMON_SQUEEZY_CHECKOUT_URL

    def donate_url(self) -> str:
        return (
            self.config.get("donate_url")
            or self.config.get("lemonsqueezy_donate_url")
            or LEMON_SQUEEZY_DONATE_URL
        )


def generate_offline_key(part1: str, part2: str) -> str:
    """Helper for you to mint offline-valid keys (run in a REPL)."""
    part1 = part1.upper()
    part2 = part2.upper()
    body = f"{part1}-{part2}"
    digest = hashlib.sha256(f"GrabbyVault|{body}".encode()).hexdigest()[:4].upper()
    return f"GV-{part1}-{part2}-{digest}"
