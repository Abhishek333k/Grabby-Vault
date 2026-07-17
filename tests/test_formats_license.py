"""Unit tests — formats + license clamp (no network)."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from core.formats import resolve_preset, QUALITY_PRESETS, DEFAULT_PRESET_ID
from core.utils import is_http_url, sanitize_filename, human_bytes
from core.license_manager import LicenseManager, FREE_PRESET_IDS


class FormatsTests(unittest.TestCase):
    def test_default_preset(self):
        p = resolve_preset(None)
        self.assertEqual(p["id"], DEFAULT_PRESET_ID)

    def test_1080_has_height(self):
        p = resolve_preset("1080")
        self.assertIn("1080", p["format"])

    def test_legacy_map(self):
        p = resolve_preset("bestvideo[height<=720]+bestaudio/best")
        self.assertEqual(p["id"], "720")

    def test_presets_nonempty(self):
        self.assertGreater(len(QUALITY_PRESETS), 3)


class UtilsTests(unittest.TestCase):
    def test_http(self):
        self.assertTrue(is_http_url("https://example.com/a"))
        self.assertFalse(is_http_url("ftp://x"))
        self.assertFalse(is_http_url(""))

    def test_sanitize(self):
        self.assertNotIn(":", sanitize_filename('a:b*c?'))
        self.assertEqual(sanitize_filename(""), "download")

    def test_human_bytes(self):
        self.assertIn("KB", human_bytes(2048))


class LicenseClampTests(unittest.TestCase):
    def test_free_clamps_1080(self):
        lic = LicenseManager()
        # Force free-tier path for clamp logic without mutating disk forever
        was_key = lic.config.get("license_key")
        was_act = lic.config.get("license_activated")
        was_dev = lic.config.get("allow_dev_keys")
        try:
            lic.config.config["license_key"] = ""
            lic.config.config["license_activated"] = False
            lic.config.config["allow_dev_keys"] = False
            lic.config.config["pro_unlocked"] = False
            fmt, warn = lic.clamp_format("1080")
            self.assertEqual(fmt, "720")
            self.assertIsNotNone(warn)
            fmt2, warn2 = lic.clamp_format("480")
            self.assertEqual(fmt2, "480")
            self.assertIsNone(warn2)
            self.assertIn("720", FREE_PRESET_IDS)
        finally:
            lic.config.config["license_key"] = was_key
            lic.config.config["license_activated"] = was_act
            lic.config.config["allow_dev_keys"] = was_dev


if __name__ == "__main__":
    unittest.main()
