import os
import time

import pytest

os.environ["CACHE_DB"] = "test_cache.db"

from backend.cache import cache_key, clear_cache, get_cached, set_cached


@pytest.fixture(autouse=True)
def clean_cache():
    clear_cache()
    yield
    clear_cache()
    try:
        os.remove("test_cache.db")
    except FileNotFoundError:
        pass


def test_cache_key_deterministic():
    k1 = cache_key("search", {"q": "phone"})
    k2 = cache_key("search", {"q": "phone"})
    assert k1 == k2


def test_cache_key_varies():
    k1 = cache_key("search", {"q": "phone"})
    k2 = cache_key("search", {"q": "laptop"})
    assert k1 != k2


def test_set_and_get():
    set_cached("test_key", {"items": [1, 2, 3]})
    result = get_cached("test_key")
    assert result == {"items": [1, 2, 3]}


def test_get_missing():
    assert get_cached("nonexistent") is None


def test_ttl_expiry(monkeypatch):
    set_cached("exp_key", {"data": True})
    assert get_cached("exp_key") is not None

    import backend.cache as cache_mod
    monkeypatch.setattr(cache_mod, "CACHE_TTL_SECONDS", 0)
    assert get_cached("exp_key") is None
