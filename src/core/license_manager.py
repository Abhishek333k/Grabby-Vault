"""
Free / Pro licensing for GrabbyVault — Layer B (Lemon Squeezy License API).

Flow:
  1. Customer buys on Lemon Squeezy → receives license key in email
  2. Paste key in app → POST /v1/licenses/activate (instance = this machine)
  3. On later launches → POST /v1/licenses/validate with instance_id
  4. Offline grace: if previously activated, stay Pro for N days without net

Docs: https://docs.lemonsqueezy.com/api/license-api
  Activate/Validate/Deactivate do NOT require an API key — only the license key.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from core.config_manager import ConfigManager
from core.formats import resolve_preset
from core.logging_setup import get_logger
from core.paths import app_root

log = get_logger("grabbyvault.license")

LS_ACTIVATE = "https://api.lemonsqueezy.com/v1/licenses/activate"
LS_VALIDATE = "https://api.lemonsqueezy.com/v1/licenses/validate"
LS_DEACTIVATE = "https://api.lemonsqueezy.com/v1/licenses/deactivate"

# Defaults — override in config.json with your real storefront links
LEMON_SQUEEZY_CHECKOUT_URL = "https://store.silenvault.com"
LEMON_SQUEEZY_DONATE_URL = "https://store.silenvault.com/sponsor/"

# Local dev only (disable for public release via config allow_dev_keys=false)
DEV_PRO_KEYS = {
    "GV-PRO-DEV-UNLOCK",
    "GV-TEST-PRO-0000",
}

FREE_MAX_CONCURRENT = 1
PRO_MAX_CONCURRENT = 5
FREE_PRESET_IDS = {"720", "480", "audio_mp3", "audio_m4a"}

# Stay Pro offline this long after last successful online check (seconds)
OFFLINE_GRACE_SECONDS = 14 * 24 * 3600


def _machine_instance_name() -> str:
    """
    Stable-ish label for this PC (shown in LS dashboard).
    Not unbreakable DRM — just seat tracking for activation_limit.
    """
    host = platform.node() or "pc"
    # Prefer Windows MachineGuid when available
    mid = ""
    if os.name == "nt":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            mid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
        except OSError:
            mid = ""
    raw = f"{host}|{mid}|{platform.system()}|{platform.machine()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    safe_host = re.sub(r"[^A-Za-z0-9_-]", "", host)[:24] or "pc"
    return f"GrabbyVault-{safe_host}-{digest}"


def _ls_post(url: str, fields: dict[str, str], timeout: float = 20.0) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "GrabbyVault/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"error": body or str(e)}
        parsed.setdefault("http_status", e.code)
        return parsed
    except Exception as e:
        return {"error": str(e), "network_error": True}


class LicenseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.config = ConfigManager()
        self._instance_name = _machine_instance_name()

    def refresh(self):
        self.config = ConfigManager()
        self.config.load_config()

    @property
    def license_key(self) -> str:
        return (self.config.get("license_key") or "").strip()

    @property
    def instance_id(self) -> str:
        return (self.config.get("license_instance_id") or "").strip()

    @property
    def allow_dev_keys(self) -> bool:
        return self.config.get("allow_dev_keys", True) is not False

    def _dev_or_offline_key(self, key: str) -> bool:
        k = key.upper().replace(" ", "")
        if self.allow_dev_keys and k in DEV_PRO_KEYS:
            return True
        if self.allow_dev_keys and self._offline_key_valid(k):
            return True
        if self.config.get("pro_unlocked") is True:
            return True
        return False

    def _offline_key_valid(self, key: str) -> bool:
        m = re.fullmatch(r"GV-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})", key)
        if not m:
            return False
        body = f"{m.group(1)}-{m.group(2)}"
        digest = hashlib.sha256(f"GrabbyVault|{body}".encode()).hexdigest()[:4].upper()
        return digest == m.group(3)

    def _cache_ok(self) -> bool:
        """Previously activated online + within grace period."""
        if not self.config.get("license_activated"):
            return False
        if not self.license_key:
            return False
        last = float(self.config.get("license_last_check") or 0)
        if last <= 0:
            return False
        return (time.time() - last) < OFFLINE_GRACE_SECONDS

    def _product_id_allowed(self, meta: dict | None) -> bool:
        """Optional: only accept keys for configured LS product id(s)."""
        allowed = self.config.get("lemonsqueezy_product_ids") or []
        if not allowed:
            return True  # no filter configured
        if isinstance(allowed, str):
            allowed = [a.strip() for a in allowed.split(",") if a.strip()]
        if not meta:
            return True
        pid = meta.get("product_id")
        try:
            return str(pid) in [str(x) for x in allowed]
        except Exception:
            return True

    @property
    def is_pro(self) -> bool:
        if self.config.get("pro_unlocked") is True:
            return True
        key = self.license_key
        if not key:
            return False
        if self._dev_or_offline_key(key):
            return True
        if self.config.get("license_activated") and self._cache_ok():
            return True
        # Activated flag but grace expired — still treat as pro offline until
        # next online revalidate fails (generous UX for travelers)
        if self.config.get("license_activated") and self.instance_id:
            return True
        return False

    def activate(self, key: str) -> tuple[bool, str]:
        """
        Activate a license on this machine (dev keys local, LS keys online).
        """
        raw = (key or "").strip()
        if not raw:
            return False, "Enter a license key."

        # Normalize: LS keys are usually UUID-like; keep case from user for API
        # but strip spaces
        key_api = raw.replace(" ", "")
        key_upper = key_api.upper()

        # Dev / offline paths
        if self._dev_or_offline_key(key_upper):
            self.config.set("license_key", key_upper)
            self.config.set("license_activated", True)
            self.config.set("license_instance_id", "dev-local")
            self.config.set("license_last_check", time.time())
            self.config.set("pro_unlocked", False)
            return True, "Pro activated (developer key)."

        # Lemon Squeezy activate
        instance_name = self._instance_name
        log.info("Activating LS license instance=%s", instance_name)
        resp = _ls_post(
            LS_ACTIVATE,
            {"license_key": key_api, "instance_name": instance_name},
        )

        if resp.get("network_error"):
            return (
                False,
                f"Network error — connect to the internet to activate.\n{resp.get('error', '')}",
            )

        # Already activated on this instance name? Try validate path
        error = resp.get("error")
        activated = resp.get("activated") is True

        if not activated and error:
            # Common: activation limit / already active — try validate if we have id
            err_l = str(error).lower()
            if "already" in err_l or "activated" in err_l:
                # Re-validate: customer reinstall with same machine name may work
                # after storing; try validate without instance first
                v = _ls_post(LS_VALIDATE, {"license_key": key_api})
                if v.get("valid") is True:
                    return self._commit_ls_success(key_api, v, note="License valid.")
            return False, f"Activation failed: {error}"

        if not activated:
            return False, f"Activation failed: {resp.get('error') or 'unknown error'}"

        if not self._product_id_allowed(resp.get("meta")):
            return False, "This license is not valid for GrabbyVault."

        return self._commit_ls_success(
            key_api,
            resp,
            note="Pro activated. Thank you for supporting SilenVault!",
        )

    def _commit_ls_success(
        self, key_api: str, resp: dict, note: str
    ) -> tuple[bool, str]:
        inst = resp.get("instance") or {}
        instance_id = inst.get("id") or self.instance_id or ""
        self.config.set("license_key", key_api)
        self.config.set("license_activated", True)
        self.config.set("license_instance_id", instance_id)
        self.config.set("license_last_check", time.time())
        self.config.set("license_meta", resp.get("meta") or {})
        # Clear blanket override
        self.config.set("pro_unlocked", False)
        log.info("License activated instance_id=%s", instance_id)
        return True, note

    def revalidate_online(self) -> tuple[bool, str]:
        """
        Periodic check. Call on app start (background) if activated.
        """
        key = self.license_key
        if not key or self._dev_or_offline_key(key.upper()):
            return True, "dev/local"

        fields = {"license_key": key}
        if self.instance_id and self.instance_id != "dev-local":
            fields["instance_id"] = self.instance_id

        resp = _ls_post(LS_VALIDATE, fields)
        if resp.get("network_error"):
            if self._cache_ok() or self.config.get("license_activated"):
                return True, "offline grace"
            return False, "offline and no prior activation"

        if resp.get("valid") is True:
            self.config.set("license_last_check", time.time())
            if resp.get("instance") and resp["instance"].get("id"):
                self.config.set("license_instance_id", resp["instance"]["id"])
            return True, "valid"

        # Invalid — revoke local
        log.warning("License revalidate failed: %s", resp.get("error"))
        self.config.set("license_activated", False)
        return False, str(resp.get("error") or "invalid")

    def deactivate_online(self) -> tuple[bool, str]:
        key = self.license_key
        iid = self.instance_id
        if not key or not iid or iid == "dev-local":
            self.deactivate_local()
            return True, "Local license cleared."

        resp = _ls_post(
            LS_DEACTIVATE, {"license_key": key, "instance_id": iid}
        )
        self.deactivate_local()
        if resp.get("deactivated") is True:
            return True, "License deactivated on this device."
        return True, f"Local cleared. Server: {resp.get('error') or 'ok'}"

    def deactivate_local(self):
        self.config.set("license_key", "")
        self.config.set("license_activated", False)
        self.config.set("license_instance_id", "")
        self.config.set("license_last_check", 0)
        self.config.set("pro_unlocked", False)

    def deactivate(self):
        self.deactivate_local()

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
        preset = resolve_preset(format_str)
        if self.is_pro:
            return (
                preset["id"] if preset["id"] != "custom" else (format_str or "best"),
                None,
            )

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

    def store_url(self) -> str:
        return self.config.get("store_url") or "https://store.silenvault.com"

    def developer_url(self) -> str:
        return self.config.get("developer_url") or "https://store.silenvault.com/about/"

    def support_email(self) -> str:
        return self.config.get("support_email") or "support@silenvault.com"

    def instance_label(self) -> str:
        return self._instance_name


def generate_offline_key(part1: str, part2: str) -> str:
    part1 = part1.upper()
    part2 = part2.upper()
    body = f"{part1}-{part2}"
    digest = hashlib.sha256(f"GrabbyVault|{body}".encode()).hexdigest()[:4].upper()
    return f"GV-{part1}-{part2}-{digest}"
