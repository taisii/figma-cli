import json
import os

from src.cache_manager import CacheManager


CACHE_FILE = "test_cache.json"


def setup_function():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def teardown_function():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def test_save_and_load_cache():
    """キャッシュの保存と読み込みをテストする"""
    data_to_save = [{"id": "1", "text": "test"}]
    CacheManager.save_cache(data_to_save, CACHE_FILE)

    assert os.path.exists(CACHE_FILE)

    loaded_data = CacheManager.load_cache(CACHE_FILE)
    assert loaded_data == data_to_save


def test_load_nonexistent_cache():
    """存在しないキャッシュファイルを読み込んだ場合にNoneが返ることをテストする"""
    loaded_data = CacheManager.load_cache("nonexistent_file.json")
    assert loaded_data is None
