"""
GrabbyVault Pro licensing — Lemon Squeezy License API (production).

Official API (no API key required on these endpoints):
  POST https://api.lemonsqueezy.com/v1/licenses/activate
    body: license_key, instance_name
  POST https://api.lemonsqueezy.com/v1/licenses/validate
    body: license_key, instance_id? (optional)
  POST https://api.lemonsqueezy.com/v1/licenses/deactivate
    body: license_key, instance_id

Headers: Accept: application/json
         Content-Type: application/x-www-form-urlencoded
Rate limit: 60 req/min

License key status: inactive | active | expired | disabled
Docs:
  https://docs.lemonsqueezy.com/api/license-api
  https://docs.lemonsqueezy.com/api/license-api/activate-license-key
  https://docs.lemonsqueezy.com/api/license-api/validate-license-key
  https://docs.lemonsqueezy.com/api/license-api/deactivate-license-key
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from core.config_manager import ConfigManager
from core.formats import resolve_preset
from core.logging_setup import get_logger
from core.paths import is_frozen

log = get_logger("grabbyvault.license")

LS_BASE = "https://api.lemonsqueezy.com/v1/licenses"
LS_ACTIVATE = f"{LS_BASE}/activate"
LS_VALIDATE = f"{LS_BASE}/validate"
LS_DEACTIVATE = f"{LS_BASE}/deactivate"

LEMON_SQUEEZY_CHECKOUT_URL = "https://store.silenvault.com"
LEMON_SQUEEZY_DONATE_URL = "https://store.silenvault.com/sponsor/"

# Local development only — never enabled in frozen production builds unless forced
DEV_PRO_KEYS = {
    "GV-PRO-DEV-UNLOCK",
    "GV-TEST-PRO-0000",
}

FREE_MAX_CONCURRENT = 1
PRO_MAX_CONCURRENT = 5
FREE_PRESET_IDS = {"720", "480", "audio_mp3", "audio_m4a"}

OFFLINE_GRACE_SECONDS = 14 * 24 * 3600
SINGLE_SEAT_OFFLINE_GRACE = 6 * 3600
DEFAULT_HEARTBEAT_SECONDS = 180

# Simple client-side rate limit cushion (LS = 60/min)
_MIN_REQUEST_INTERVAL = 1.05

# License statuses from LS docs
_STATUS_OK = frozenset({"inactive", "active"})
_STATUS_DEAD = frozenset({"expired", "disabled"})


def _machine_fingerprint() -> str:
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
    """instance_name sent to LS activate (label in dashboard)."""
    host = platform.node() or "pc"
    safe_host = re.sub(r"[^A-Za-z0-9_-]", "", host)[:24] or "pc"
    digest = _machine_fingerprint()[:12]
    return f"GrabbyVault-{safe_host}-{digest}"


class LemonSqueezyClient:
    """
    Thin client for the public License API.
    Uses form-urlencoded POST as required by Lemon Squeezy.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _throttle(self):
        with self._lock:
            now = time.time()
            wait = _MIN_REQUEST_INTERVAL - (now - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.time()

    def post(self, url: str, fields: dict[str, str], timeout: float = 25.0) -> dict:
        self._throttle()
        # Drop empty optional fields
        clean = {k: v for k, v in fields.items() if v is not None and str(v) != ""}
        data = urllib.parse.urlencode(clean).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "GrabbyVault/1.0 (SilenVault; +https://store.silenvault.com)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body else {}
                parsed["_http_status"] = getattr(resp, "status", 200)
                return parsed
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"error": body or str(e)}
            parsed["_http_status"] = e.code
            if "error" not in parsed or parsed.get("error") is None:
                # Ensure error field for 4xx
                if e.code == 422:
                    parsed.setdefault("error", "A required field was invalid or missing.")
                elif e.code == 404:
                    parsed.setdefault("error", "License key or instance not found.")
                elif e.code == 400:
                    parsed.setdefault("error", "Lemon Squeezy rejected the request.")
                else:
                    parsed.setdefault("error", f"HTTP {e.code}")
            return parsed
        except Exception as e:
            return {"error": str(e), "network_error": True, "_http_status": 0}

    def activate(self, license_key: str, instance_name: str) -> dict:
        return self.post(
            LS_ACTIVATE,
            {"license_key": license_key, "instance_name": instance_name},
        )

    def validate(self, license_key: str, instance_id: str | None = None) -> dict:
        fields: dict[str, str] = {"license_key": license_key}
        if instance_id:
            fields["instance_id"] = instance_id
        return self.post(LS_VALIDATE, fields)

    def deactivate(self, license_key: str, instance_id: str) -> dict:
        return self.post(
            LS_DEACTIVATE,
            {"license_key": license_key, "instance_id": instance_id},
        )


def _license_key_usable(lk: dict | None) -> tuple[bool, str]:
    """Interpret license_key.status from LS response."""
    if not lk:
        return True, "no key object"  # let top-level valid/activated decide
    status = (lk.get("status") or "").lower()
    if status in _STATUS_DEAD:
        return False, f"License is {status}."
    exp = lk.get("expires_at")
    if exp:
        # ISO8601 — compare loosely via prefix date if parse fails
        try:
            # "2022-01-24T14:15:07.000000Z"
            from datetime import datetime, timezone

            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if exp_dt < datetime.now(timezone.utc):
                return False, "License has expired."
        except Exception:
            pass
    return True, status or "ok"


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
        self.client = LemonSqueezyClient()

    def refresh(self):
        self.config = ConfigManager()
        self.config.load_config()

    def set_demote_callback(self, cb: Callable[[str], None] | None):
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
        """
        Production (frozen) builds: never accept dev keys unless
        GRABBYVAULT_ALLOW_DEV_KEYS=1 is set in the environment.
        Dev source runs: allow_dev_keys config may be true.
        """
        if os.environ.get("GRABBYVAULT_ALLOW_DEV_KEYS", "").strip() == "1":
            return True
        if is_frozen():
            return False
        return self.config.get("allow_dev_keys", False) is True

    def _stored_fp(self) -> str:
        return (self.config.get("license_machine_fp") or "").strip()

    def _fp_matches(self) -> bool:
        stored = self._stored_fp()
        return bool(stored) and stored == self._fp

    def _dev_or_offline_key(self, key: str) -> bool:
        if not self.allow_dev_keys:
            return False
        k = key.upper().replace(" ", "")
        if k in DEV_PRO_KEYS:
            return True
        if self._offline_key_valid(k):
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
                self.config.get(
                    "license_single_seat_grace_seconds", SINGLE_SEAT_OFFLINE_GRACE
                )
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

    def _variant_id_allowed(self, meta: dict | None) -> bool:
        allowed = self.config.get("lemonsqueezy_variant_ids") or []
        if not allowed:
            return True
        if isinstance(allowed, str):
            allowed = [a.strip() for a in allowed.split(",") if a.strip()]
        if not meta:
            return True
        return str(meta.get("variant_id")) in [str(x) for x in allowed]

    def _meta_allowed(self, meta: dict | None) -> tuple[bool, str]:
        if not self._product_id_allowed(meta):
            return False, "This license is not for GrabbyVault (product mismatch)."
        if not self._variant_id_allowed(meta):
            return False, "This license is not for GrabbyVault (variant mismatch)."
        return True, ""

    def _is_dev_pro(self) -> bool:
        key = self.license_key
        if not key:
            return self.config.get("pro_unlocked") is True and self.allow_dev_keys
        return self._dev_or_offline_key(key.upper().replace(" ", ""))

    @property
    def is_pro(self) -> bool:
        if self.config.get("pro_unlocked") is True and self.allow_dev_keys:
            return True
        key = self.license_key
        if not key:
            return False
        if self._dev_or_offline_key(key.upper().replace(" ", "")):
            return True
        if not self.config.get("license_activated"):
            return False
        if self.single_seat and not self._fp_matches():
            return False
        if self.single_seat and not self._within_grace():
            return False
        return True

    def demote(self, reason: str = "License no longer valid on this device."):
        with self._lock:
            was = bool(self.config.get("license_activated")) or self.is_pro
            self.config.set("license_activated", False)
            log.warning("Pro demoted: %s", reason)
        if was and self._on_demoted:
            try:
                self._on_demoted(reason)
            except Exception as e:
                log.error("demote callback: %s", e)

    def activate(self, key: str) -> tuple[bool, str]:
        """
        Activate license on this machine via LS /v1/licenses/activate.
        Requires: license_key + instance_name
        Success: activated=true, instance.id stored for validate/deactivate
        """
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
                    "license_status": "active",
                    "license_test_mode": True,
                }
            )
            self.start_heartbeat()
            return True, "Pro activated (developer key) on this PC only."

        instance_name = self._instance_name
        log.info(
            "LS activate instance_name=%s single_seat=%s",
            instance_name,
            self.single_seat,
        )
        resp = self.client.activate(key_api, instance_name)

        if resp.get("network_error"):
            return (
                False,
                "Network error — connect to the internet to activate.\n"
                f"{resp.get('error', '')}",
            )

        # Parse license_key status if present
        lk = resp.get("license_key") or {}
        ok_status, status_msg = _license_key_usable(lk)
        if not ok_status:
            return False, status_msg

        activated = resp.get("activated") is True
        error = resp.get("error")

        if not activated:
            err = error or "Activation failed."
            err_l = str(err).lower()
            if any(
                w in err_l
                for w in ("limit", "activation", "maximum", "reached", "already")
            ):
                return (
                    False,
                    f"{err}\n\n"
                    "This key is already active on another device "
                    f"(usage {lk.get('activation_usage')}/{lk.get('activation_limit')}).\n"
                    "Use “Take over this PC” to move the seat here, or release "
                    "the seat on the other machine first.",
                )
            return False, f"Activation failed: {err}"

        ok_meta, meta_err = self._meta_allowed(resp.get("meta"))
        if not ok_meta:
            # Activated by mistake for wrong product — try deactivate immediately
            inst = (resp.get("instance") or {}).get("id")
            if inst:
                self.client.deactivate(key_api, inst)
            return False, meta_err

        return self._commit_ls_success(
            key_api,
            resp,
            note=(
                "Pro activated on this PC via Lemon Squeezy.\n"
                "Single-seat: only this device uses Pro at a time."
            ),
        )

    def take_over_device(self, key: str | None = None) -> tuple[bool, str]:
        """
        Move seat to this PC:
          1) deactivate stored instance_id (LS /deactivate)
          2) activate with this machine's instance_name
        """
        key_api = (key or self.license_key or "").replace(" ", "").strip()
        if not key_api:
            return False, "Enter a license key first."

        if self._dev_or_offline_key(key_api.upper()):
            return self.activate(key_api)

        iid = self.instance_id
        if iid and iid != "dev-local":
            log.info("Take-over: LS deactivate instance_id=%s", iid)
            dresp = self.client.deactivate(key_api, iid)
            log.info(
                "Take-over deactivate: deactivated=%s error=%s",
                dresp.get("deactivated"),
                dresp.get("error"),
            )
            self.config.update(
                {"license_instance_id": "", "license_activated": False}
            )

        ok, msg = self.activate(key_api)
        if ok:
            return (
                True,
                "Seat moved to this PC. Other devices lose Pro on their next check.\n"
                + msg,
            )
        return (
            False,
            msg
            + "\n\nIf this still fails, open Lemon Squeezy → Orders → "
            "deactivate old instances, then Activate again.",
        )

    def _commit_ls_success(
        self, key_api: str, resp: dict, note: str
    ) -> tuple[bool, str]:
        inst = resp.get("instance") or {}
        instance_id = inst.get("id") or ""
        if not instance_id:
            return False, "Activation succeeded but no instance.id returned."

        lk = resp.get("license_key") or {}
        meta = resp.get("meta") or {}

        self.config.update(
            {
                "license_key": key_api,
                "license_activated": True,
                "license_instance_id": instance_id,
                "license_machine_fp": self._fp,
                "license_last_check": time.time(),
                "license_meta": meta,
                "license_status": lk.get("status") or "active",
                "license_expires_at": lk.get("expires_at"),
                "license_activation_limit": lk.get("activation_limit"),
                "license_activation_usage": lk.get("activation_usage"),
                "license_product_name": meta.get("product_name"),
                "license_customer_email": meta.get("customer_email"),
                "pro_unlocked": False,
            }
        )
        log.info(
            "LS activated instance_id=%s status=%s product=%s",
            instance_id,
            lk.get("status"),
            meta.get("product_name"),
        )
        self.start_heartbeat()
        return True, note

    def revalidate_online(self, *, force_demote: bool = True) -> tuple[bool, str]:
        """
        Validate via LS /v1/licenses/validate with instance_id when known.
        Docs: if instance_id omitted, instance is null and only the key is checked.
        We always send instance_id after activate so the seat stays bound.
        """
        key = self.license_key
        if not key:
            return False, "no key"

        if self._dev_or_offline_key(key.upper().replace(" ", "")):
            self.config.update(
                {
                    "license_last_check": time.time(),
                    "license_machine_fp": self._fp,
                }
            )
            return True, "dev/local"

        if self.single_seat and self._stored_fp() and not self._fp_matches():
            if force_demote:
                self.demote("License is bound to another PC. Use Take over this PC.")
            return False, "wrong machine"

        iid = self.instance_id if self.instance_id != "dev-local" else None
        resp = self.client.validate(key, iid)

        if resp.get("network_error"):
            if self._within_grace() and self._fp_matches():
                return True, "offline grace"
            if force_demote and self.single_seat and not self._within_grace():
                self.demote("Could not verify license online (single-seat timeout).")
            return False, "offline"

        lk = resp.get("license_key") or {}
        ok_status, status_msg = _license_key_usable(lk)
        if not ok_status:
            if force_demote:
                self.demote(status_msg)
            return False, status_msg

        if resp.get("valid") is not True:
            err = resp.get("error") or "License invalid."
            if force_demote:
                self.demote(str(err))
            else:
                self.config.set("license_activated", False)
            return False, str(err)

        # When instance_id was sent, instance should match
        inst = resp.get("instance")
        if iid:
            if not inst or not inst.get("id"):
                if force_demote:
                    self.demote("License instance is no longer active on this device.")
                return False, "instance missing"
            if inst.get("id") != iid:
                if force_demote:
                    self.demote("License seat is active on a different instance.")
                return False, "instance mismatch"

        ok_meta, meta_err = self._meta_allowed(resp.get("meta"))
        if not ok_meta:
            if force_demote:
                self.demote(meta_err)
            return False, meta_err

        patch = {
            "license_last_check": time.time(),
            "license_activated": True,
            "license_machine_fp": self._fp,
            "license_status": lk.get("status"),
            "license_expires_at": lk.get("expires_at"),
            "license_activation_limit": lk.get("activation_limit"),
            "license_activation_usage": lk.get("activation_usage"),
        }
        if inst and inst.get("id"):
            patch["license_instance_id"] = inst["id"]
        if resp.get("meta"):
            patch["license_meta"] = resp["meta"]
        self.config.update(patch)
        return True, "valid"

    def start_heartbeat(self):
        if not self.single_seat:
            return
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()

        def loop():
            log.info(
                "License heartbeat every %ss (LS validate)",
                self.heartbeat_seconds,
            )
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
        """LS /v1/licenses/deactivate — requires license_key + instance_id."""
        key = self.license_key
        iid = self.instance_id
        self.stop_heartbeat()
        if not key or not iid or iid == "dev-local":
            self.deactivate_local()
            return True, "Local license cleared on this PC."

        resp = self.client.deactivate(key, iid)
        self.deactivate_local()
        if resp.get("deactivated") is True:
            return True, "Seat released via Lemon Squeezy. Another PC can activate Pro."
        err = resp.get("error") or "unknown"
        return True, f"Local cleared. Server deactivate: {err}"

    def deactivate_local(self):
        self.config.update(
            {
                "license_key": "",
                "license_activated": False,
                "license_instance_id": "",
                "license_machine_fp": "",
                "license_last_check": 0,
                "license_status": "",
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
            st = self.config.get("license_status") or "active"
            return f"Pro · {st} · this PC only" if self.single_seat else f"Pro · {st}"
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
