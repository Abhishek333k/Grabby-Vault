import json
import os
import threading

from core.paths import app_root, config_path, downloads_dir


class ConfigManager:
    _instance = None
    _file_lock = threading.Lock()

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
            # Release builds should ship with False (see config.example.json)
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
            "use_acrylic": True,
            "playwright_headless": False,
            "playwright_timeout_seconds": 45,
        }
        self.config = self.load_config()
        self._migrate_absolute_dev_paths()

    def _migrate_absolute_dev_paths(self):
        """Normalize download_path to a usable portable location when needed."""
        path = self.config.get("download_path") or ""
        root = app_root()
        portable = os.path.join(root, "downloads")
        changed = False

        if path in ("downloads", "./downloads", ""):
            self.config["download_path"] = portable
            changed = True
        elif path and not os.path.isdir(path):
            # Missing folder: prefer creating portable default over dead absolute path
            parent = os.path.dirname(path)
            if not parent or not os.path.isdir(parent):
                self.config["download_path"] = portable
                changed = True

        if changed:
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
            if isinstance(data, dict):
                config.update(data)
            self.config = config
            return self.config
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self.default_config.copy()
            return self.config

    def _write(self, config_dict):
        with self._file_lock:
            try:
                parent = os.path.dirname(self.config_file) or "."
                os.makedirs(parent, exist_ok=True)
                tmp = self.config_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(config_dict, f, indent=4)
                os.replace(tmp, self.config_file)
            except Exception as e:
                print(f"Error saving config: {e}")

    def save_config(self, config_dict=None):
        if config_dict:
            self.config.update(config_dict)
        self._write(self.config)

    def update(self, values: dict):
        """Batch update many keys with a single disk write."""
        self.config.update(values)
        self._write(self.config)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_download_path(self) -> str:
        return downloads_dir(self.get("download_path"))
