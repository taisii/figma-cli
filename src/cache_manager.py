import json
import os

class CacheManager:

    @staticmethod
    def save_cache(data, cache_file):
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_cache(cache_file):
        if not os.path.exists(cache_file):
            return None
        with open(cache_file, "r") as f:
            return json.load(f)
