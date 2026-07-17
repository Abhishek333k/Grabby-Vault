"""
Free / Pro licensing for GrabbyVault — Lemon Squeezy License API + single-seat.

Single-seat (Netflix-style) model:
  - Lemon Squeezy product should use activation_limit = 1 (dashboard).
  - This app binds Pro to a machine fingerprint so copying config.json
    to another PC does NOT grant Pro.
  - While the app is open, a heartbeat re-validates the license online.
    If the seat is released / stolen / revoked → Pro drops immediately.
  - "Take over this PC" deactivates the stored instance then re-activates here.

Docs: https://docs.lemonsqueezy.com/api/license-api
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from core.config_manager import ConfigManager
from core.formats import resolve_preset
from core.logging_setup import get_logger

log = get_logger("grabbyvault.license")

LS_ACTIVATE = "https://api.lemonsqueezy.com/v1/licenses/activate"
LS_VALIDATE = "https://api.lemonsqueezy.com/v1/licenses/validate"
LS_DEACTIVATE = "https://api.lemonsqueezy.com/v1/licenses/deactivate"

LEMON_SQUEEZY_CHECKOUT_URL = "https://store.silenvault.com"
LEMON_SQUEEZY_DONATE_URL = "https://store.silenvault.com/sponsor/"

DEV_PRO_KEYS = {
    "GV-PRO-DEV-UNLOCK",
    "GV-TEST-PRO-0000",
}

FREE_MAX_CONCURRENT = 1
PRO_MAX_CONCURRENT = 5
FREE_PRESET_IDS = {"720", "480", "audio_mp3", "audio_m4a"}

# Offline grace when single-seat is OFF (days)
OFFLINE_GRACE_SECONDS = 14 * 24 * 3600
# Offline grace when single-seat is ON — short; must recheck often
SINGLE_SEAT_OFFLINE_GRACE = 6 * 3600  # 6 hours max without successful online check
DEFAULT_HEARTBEAT_SECONDS = 180  # 3 minutes while app is open


def _machine_fingerprint() -> str:
    """Stable id for this hardware (binds Pro to one PC)."""
    host = platform.node() or "pc"
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
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _machine_instance_name() -> str:
    host = platform.node() or "pc"
    safe_host = re.sub(r"[^A-Za-z0-9_-]", "", host)[:24] or "pc"
    digest = _machine_fingerprint()[:12]
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
        self._fp = _machine_fingerprint()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._on_demoted: Callable[[str], None] | None = None
        self._lock = threading.Lock()

    def refresh(self):
        self.config = ConfigManager()
        self.config.load_config()

    def set_demote_callback(self, cb: Callable[[str], None] | None):
        """UI hook when Pro is revoked mid-session."""
        self._on_demoted = cb

    @property
    def single_seat(self) -> bool:
        return self.config.get("license_single_seat", True) is not False

    @property
    def heartbeat_seconds(self) -> int:
        try:
            return max(60, int(self.config.get("license_heartbeat_seconds", DEFAULT_HEARTBEAT_SECONDS)))
        except (TypeError, ValueError):
            return DEFAULT_HEARTBEAT_SECONDS

    @property
    def license_key(self) -> str:
        return (self.config.get("license_key") or "").strip()

    @property
    def instance_id(self) -> str:
        return (self.config.get("license_instance_id") or "").strip()

    @property
    def allow_dev_keys(self) -> bool:
        return self.config.get("allow_dev_keys", True) is not False

    def _stored_fp(self) -> str:
        return (self.config.get("license_machine_fp") or "").strip()

    def _fp_matches(self) -> bool:
        stored = self._stored_fp()
        if not stored:
            return False
        return stored == self._fp

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

    def _grace_seconds(self) -> float:
        if self.single_seat:
            return float(
                self.config.get("license_single_seat_grace_seconds", SINGLE_SEAT_OFFLINE_GRACE)
            )
        return float(OFFLINE_GRACE_SECONDS)

    def _within_grace(self) -> bool:
        last = float(self.config.get("license_last_check") or 0)
        if last <= 0:
            return False
        return (time.time() - last) < self._grace_seconds()

    def _product_id_allowed(self, meta: dict | None) -> bool:
        allowed = self.config.get("lemonsqueezy_product_ids") or []
        if not allowed:
            return True
        if isinstance(allowed, str):
            allowed = [a.strip() for a in allowed.split(",") if a.strip()]
        if not meta:
            return True
        return str(meta.get("product_id")) in [str(x) for x in allowed]

    def _is_dev_pro(self) -> bool:
        key = self.license_key
        if not key:
            return self.config.get("pro_unlocked") is True
        return self._dev_or_offline_key(key.upper().replace(" ", ""))

    @property
    def is_pro(self) -> bool:
        if self.config.get("pro_unlocked") is True:
            return True
        key = self.license_key
        if not key:
            return False

        # Dev keys: always Pro on this machine (dev only)
        if self._dev_or_offline_key(key.upper().replace(" ", "")):
            return True

        # Real LS seat: must be activated + this machine + not expired grace
        if not self.config.get("license_activated"):
            return False
        if self.single_seat and not self._fp_matches():
            # Config was copied to another PC — deny until re-activate / take over
            return False
        if self._within_grace() or self.config.get("license_activated"):
            # Activated + fp ok; grace softens offline. Heartbeat hardens online.
            if self.single_seat and not self._within_grace():
                # Past grace without online check → not Pro until revalidate
                return False
            return True
        return False

    def demote(self, reason: str = "License no longer valid on this device."):
        """Drop Pro mid-session (seat lost / revoked / wrong PC)."""
        with self._lock:
            was = self.config.get("license_activated") or self.is_pro
            self.config.set("license_activated", False)
            # Keep key so user can try take-over; clear instance binding softness
            log.warning("Pro demoted: %s", reason)
        if was and self._on_demoted:
            try:
                self._on_demoted(reason)
            except Exception as e:
                log.error("demote callback: %s", e)

    def activate(self, key: str) -> tuple[bool, str]:
        raw = (key or "").strip()
        if not raw:
            return False, "Enter a license key."

        key_api = raw.replace(" ", "")
        key_upper = key_api.upper()

        if self._dev_or_offline_key(key_upper):
            self.config.update(
                {
                    "license_key": key_upper,
                    "license_activated": True,
                    "license_instance_id": "dev-local",
                    "license_machine_fp": self._fp,
                    "license_last_check": time.time(),
                    "pro_unlocked": False,
                }
            )
            self.start_heartbeat()
            return True, "Pro activated (developer key) on this PC only."

        instance_name = self._instance_name
        log.info("Activating LS license instance=%s single_seat=%s", instance_name, self.single_seat)
        resp = _ls_post(
            LS_ACTIVATE,
            {"license_key": key_api, "instance_name": instance_name},
        )

        if resp.get("network_error"):
            return (
                False,
                "Network error — connect to the internet to activate.\n"
                f"{resp.get('error', '')}",
            )

        activated = resp.get("activated") is True
        error = resp.get("error")

        if not activated and error:
            err_l = str(error).lower()
            # Seat full — guide take-over
            if any(
                w in err_l
                for w in ("limit", "activation", "maximum", "already", "reached")
            ):
                return (
                    False,
                    "This license is already active on another device "
                    f"(limit reached).\n\n"
                    f"Server: {error}\n\n"
                    "Use “Take over this PC” to move the single seat here "
                    "(the other device will lose Pro). "
                    "In Lemon Squeezy, set Activation limit = 1 for one screen.",
                )
            v = _ls_post(LS_VALIDATE, {"license_key": key_api})
            if v.get("valid") is True and self._fp_matches() is False:
                # Valid key but not this machine — need activate or take over
                pass
            return False, f"Activation failed: {error}"

        if not activated:
            return False, f"Activation failed: {resp.get('error') or 'unknown error'}"

        if not self._product_id_allowed(resp.get("meta")):
            return False, "This license is not valid for GrabbyVault."

        return self._commit_ls_success(
            key_api,
            resp,
            note=(
                "Pro activated on this PC only.\n"
                "If someone uses the key elsewhere, this seat can be taken over "
                "and you will drop to Free (single-device mode)."
            ),
        )

    def take_over_device(self, key: str | None = None) -> tuple[bool, str]:
        """
        Netflix-style: free the seat (deactivate stored/remote instance) then
        activate on THIS machine. Other PC loses Pro on next heartbeat.
        """
        key_api = (key or self.license_key or "").replace(" ", "").strip()
        if not key_api:
            return False, "Enter a license key first."

        if self._dev_or_offline_key(key_api.upper()):
            return self.activate(key_api)

        # 1) Deactivate existing instance if we know it (config or after failed share)
        iid = self.instance_id
        if iid and iid != "dev-local":
            log.info("Take-over: deactivating instance %s", iid)
            _ls_post(LS_DEACTIVATE, {"license_key": key_api, "instance_id": iid})
            self.config.set("license_instance_id", "")
            self.config.set("license_activated", False)

        # 2) Also try validate to discover nothing more without API key —
        #    then activate fresh on this machine name
        ok, msg = self.activate(key_api)
        if ok:
            return True, "Seat moved to this PC. Other devices lose Pro on their next check.\n" + msg
        return False, (
            msg
            + "\n\nIf take-over failed, open Lemon Squeezy → Orders → "
            "deactivate old license instances, then Activate again."
        )

    def _commit_ls_success(
        self, key_api: str, resp: dict, note: str
    ) -> tuple[bool, str]:
        inst = resp.get("instance") or {}
        instance_id = inst.get("id") or self.instance_id or ""
        self.config.update(
            {
                "license_key": key_api,
                "license_activated": True,
                "license_instance_id": instance_id,
                "license_machine_fp": self._fp,
                "license_last_check": time.time(),
                "license_meta": resp.get("meta") or {},
                "pro_unlocked": False,
            }
        )
        log.info("License activated instance_id=%s fp=%s…", instance_id, self._fp[:8])
        self.start_heartbeat()
        return True, note

    def revalidate_online(self, *, force_demote: bool = True) -> tuple[bool, str]:
        key = self.license_key
        if not key:
            return False, "no key"

        if self._dev_or_offline_key(key.upper().replace(" ", "")):
            self.config.set("license_last_check", time.time())
            self.config.set("license_machine_fp", self._fp)
            return True, "dev/local"

        if self.single_seat and self._stored_fp() and not self._fp_matches():
            if force_demote:
                self.demote("License is bound to another PC. Use Take over this PC.")
            return False, "wrong machine"

        fields = {"license_key": key}
        if self.instance_id and self.instance_id != "dev-local":
            fields["instance_id"] = self.instance_id

        resp = _ls_post(LS_VALIDATE, fields)
        if resp.get("network_error"):
            if self._within_grace() and self._fp_matches():
                return True, "offline grace"
            if force_demote and self.single_seat and not self._within_grace():
                self.demote("Could not verify license online (single-seat timeout).")
            return False, "offline"

        if resp.get("valid") is True:
            # Confirm instance still ours when provided
            inst = resp.get("instance")
            if inst and self.instance_id and inst.get("id") and inst.get("id") != self.instance_id:
                if force_demote:
                    self.demote("License seat is active on a different instance.")
                return False, "instance mismatch"

            self.config.set("license_last_check", time.time())
            self.config.set("license_activated", True)
            self.config.set("license_machine_fp", self._fp)
            if inst and inst.get("id"):
                self.config.set("license_instance_id", inst["id"])
            return True, "valid"

        if force_demote:
            self.demote(str(resp.get("error") or "License invalid or seat released."))
        else:
            self.config.set("license_activated", False)
        return False, str(resp.get("error") or "invalid")

    def start_heartbeat(self):
        """Background loop: keep single-seat honest while app runs."""
        if not self.single_seat:
            return
        if self._is_dev_pro() and self.allow_dev_keys:
            # Still heartbeat lightly for consistency
            pass
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()

        def loop():
            log.info(
                "License heartbeat started (every %ss, single_seat=%s)",
                self.heartbeat_seconds,
                self.single_seat,
            )
            # First check soon after start
            if not self._heartbeat_stop.wait(15):
                try:
                    self.revalidate_online(force_demote=True)
                except Exception as e:
                    log.error("heartbeat: %s", e)
            while not self._heartbeat_stop.wait(self.heartbeat_seconds):
                try:
                    if not self.license_key:
                        continue
                    ok, msg = self.revalidate_online(force_demote=True)
                    log.debug("heartbeat: %s %s", ok, msg)
                except Exception as e:
                    log.error("heartbeat: %s", e)

        self._heartbeat_thread = threading.Thread(
            target=loop, daemon=True, name="license-heartbeat"
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        self._heartbeat_stop.set()

    def deactivate_online(self) -> tuple[bool, str]:
        key = self.license_key
        iid = self.instance_id
        self.stop_heartbeat()
        if not key or not iid or iid == "dev-local":
            self.deactivate_local()
            return True, "Local license cleared on this PC."

        resp = _ls_post(LS_DEACTIVATE, {"license_key": key, "instance_id": iid})
        self.deactivate_local()
        if resp.get("deactivated") is True:
            return True, "Seat released. Another PC can activate Pro now."
        return True, f"Local cleared. Server: {resp.get('error') or 'ok'}"

    def deactivate_local(self):
        self.config.update(
            {
                "license_key": "",
                "license_activated": False,
                "license_instance_id": "",
                "license_machine_fp": "",
                "license_last_check": 0,
                "pro_unlocked": False,
            }
        )

    def deactivate(self):
        self.deactivate_local()

    def tier_label(self) -> str:
        return "PRO" if self.is_pro else "FREE"

    def seat_status_text(self) -> str:
        if self._is_dev_pro():
            return "Dev seat · this PC"
        if not self.license_key:
            return "No license"
        if self.is_pro:
            return "Pro seat active · this PC only" if self.single_seat else "Pro active"
        if self.license_key and not self._fp_matches() and self._stored_fp():
            return "Key bound to another PC — Take over to use here"
        if self.config.get("license_activated") and not self._within_grace():
            return "Seat expired offline — reconnect to verify"
        return "Free tier"

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
