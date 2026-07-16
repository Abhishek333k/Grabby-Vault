import json
import os

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.config_file = "config.json"
        self.default_config = {
            "download_path": os.path.abspath("downloads"),
            "max_concurrent_downloads": 2
        }
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_file):
            return self.default_config.copy()
        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)
                config = self.default_config.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()

    def save_config(self, config_dict=None):
        if config_dict:
            self.config.update(config_dict)
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
