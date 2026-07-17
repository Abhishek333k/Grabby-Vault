import json
import os

from core.paths import app_root, config_path, downloads_dir


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.config_file = config_path()
        root = app_root()
        self.default_config = {
            "download_path": os.path.join(root, "downloads"),
            "max_concurrent_downloads": 2,
            "default_quality": "1080",
            "license_key": "",
            "license_activated": False,
            "license_instance_id": "",
            "license_machine_fp": "",
            "license_last_check": 0,
            "license_single_seat": True,
            "license_heartbeat_seconds": 180,
            "license_single_seat_grace_seconds": 21600,
            "pro_unlocked": False,
            "allow_dev_keys": True,
            "lemonsqueezy_checkout_url": "https://store.silenvault.com",
            "lemonsqueezy_donate_url": "https://store.silenvault.com/sponsor/",
            "lemonsqueezy_product_ids": [],
            "store_url": "https://store.silenvault.com",
            "developer_url": "https://store.silenvault.com/about/",
            "support_email": "support@silenvault.com",
            "donate_url": "",
            "open_folder_on_complete": False,
            "write_subtitles": True,
            "embed_thumbnail": True,
            "show_splash": True,
        }
        self.config = self.load_config()
        self._migrate_absolute_dev_paths()

    def _migrate_absolute_dev_paths(self):
        """If download_path points at another machine path, reset to portable default."""
        path = self.config.get("download_path") or ""
        root = app_root()
        portable = os.path.join(root, "downloads")
        # Old hard-coded machine path from early dev
        if not path or not os.path.isdir(os.path.dirname(path)) and "GitHub Repos" in path:
            # keep if exists; else portable
            if not os.path.isdir(path):
                self.config["download_path"] = portable
                self.save_config()
        # Normalize relative "downloads"
        if path in ("downloads", "./downloads"):
            self.config["download_path"] = portable
            self.save_config()

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.config = self.default_config.copy()
            self._write(self.config)
            return self.config
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = self.default_config.copy()
                config.update(data)
                self.config = config
                return self.config
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self.default_config.copy()
            return self.config

    def _write(self, config_dict):
        try:
            os.makedirs(os.path.dirname(self.config_file) or ".", exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def save_config(self, config_dict=None):
        if config_dict:
            self.config.update(config_dict)
        self._write(self.config)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_download_path(self) -> str:
        return downloads_dir(self.get("download_path"))
