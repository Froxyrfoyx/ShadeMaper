import yaml
import os

class ConfigsettingManager:
    def __init__(self, config_path="configs.yaml") -> None:
        self.configpath = config_path
        self.data = self._loadconfig()
    def create_config(self):
        pass
    def _loadconfig(self):
        if not os.path.exists(self.configpath):
            return {}
        with open(self.configpath, 'r') as c:
            return yaml.safe_load(c) or {}

    def get(self, key_path, default=None):
        keys = key_path.split('.')
        val = self.data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val
