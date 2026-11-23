"""Tests for backend.rapidapi_client — all mocked, zero live API calls."""
import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend import rapidapi_client as rc


def run(coro):
    return asyncio.run(coro)


# ── Fixtures ──

@pytest.fixture(autouse=True)
def reset_module_state(tmp_path):
    """Reset module globals and point settings to temp dir."""
    rc._api_key = None
    rc._calls_today = 0
    rc._calls_date = ""
    rc._page_size = 10
    rc.SETTINGS_PATH = str(tmp_path / "rapidapi_settings.json")
    yield


@pytest.fixture
def configured():
    """Set a fake API key so is_configured() returns True."""
    rc._api_key = "test_key_long_enough_1234567890"


# ── normalize_item ──

SAMPLE_ITEM = {
    "id": "123456789012",
    "title": "iPhone 15 Pro 256GB",
    "price": "4599.00",
    "imageUrls": ["//img.alicdn.com/abc.jpg", "https://img2.example.com/def.jpg"],
    "seller": {"nick": "好卖家"},
    "city": "深圳",
    "status": "on_sale",
    "desc": "Full box, good condition",
    "condition": "95新",
    "specs": {"storage": "256GB", "battery_health": "92%"},
}


def test_normalize_item_basic():
    result = rc.normalize_item(SAMPLE_ITEM)
    assert result["id"] == "123456789012"
    assert result["title"] == "iPhone 15 Pro 256GB"
    assert result["price"] == 4599.00
    assert result["images"] == ["https://img.alicdn.com/abc.jpg", "https://img2.example.com/def.jpg"]
    assert result["seller"] == "好卖家"
    assert result["location"] == "深圳"
    assert result["status"] == "on_sale"
    assert result["source"] == "rapidapi"
    assert "123456789012" in result["url"]
    assert result["condition"] == "95新"
    assert result["specs"]["storage"] == "256GB"


def test_normalize_item_sold_status():
    item = {**SAMPLE_ITEM, "status": "已卖出"}
    assert rc.normalize_item(item)["status"] == "sold"


def test_normalize_item_price_with_symbol():
    item = {**SAMPLE_ITEM, "price": "¥1,299.50"}
    assert rc.normalize_item(item)["price"] == 1299.50


def test_normalize_item_no_price():
    item = {**SAMPLE_ITEM, "price": None}
    assert rc.normalize_item(item)["price"] is None


def test_normalize_item_numeric_price():
    item = {**SAMPLE_ITEM, "price": 888}
    assert rc.normalize_item(item)["price"] == 888.0


def test_normalize_item_nested_data():
    wrapped = {"data": SAMPLE_ITEM}
    result = rc.normalize_item(wrapped)
    assert result["id"] == "123456789012"


def test_normalize_item_string_seller():
    item = {**SAMPLE_ITEM, "seller": "plain_nick"}
    result = rc.normalize_item(item)
    assert result["seller"] == "plain_nick"


def test_normalize_item_empty_images():
    item = {**SAMPLE_ITEM, "imageUrls": []}
    assert rc.normalize_item(item)["images"] == []


def test_normalize_item_dict_images():
    item = {**SAMPLE_ITEM, "imageUrls": [{"url": "//img.example.com/a.jpg"}]}
    result = rc.normalize_item(item)
    assert result["images"] == ["https://img.example.com/a.jpg"]


# ── is_configured ──

def test_is_configured_false_when_no_key():
    assert rc.is_configured() is False


def test_is_configured_false_when_short_key():
    rc._api_key = "short"
    assert rc.is_configured() is False


def test_is_configured_true(configured):
    assert rc.is_configured() is True


# ── SORT_MAP ──

def test_sort_map_covers_ui_values():
    for ui_val in ("relevance", "price_asc", "price_desc", "deal", "newest"):
        assert ui_val in rc.SORT_MAP


# ── search_listings ──

MOCK_SEARCH_RESPONSE = {
    "data": {
        "items": [SAMPLE_ITEM, {**SAMPLE_ITEM, "id": "999", "title": "MacBook"}],
        "resolvedKeyword": "iphone 15",
        "count": 2,
    }
}


def test_search_returns_none_without_key():
    assert run(rc.search_listings("iphone")) is None


def test_search_success(configured):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_SEARCH_RESPONSE

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = run(rc.search_listings("iphone", min_price=100, sort="price_asc", personal_only=True))

    assert result is not None
    assert len(result) == 2
    assert result[0]["title"] == "iPhone 15 Pro 256GB"
    assert result[0]["source"] == "rapidapi"

    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
    assert params["keyword"] == "iphone"
    assert params["price_min"] == "100"
    assert params["sort_by"] == "priceAsc"
    assert params["personal_only"] == "true"


def test_search_fallback_on_401(configured):
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        assert run(rc.search_listings("test")) is None


def test_search_fallback_on_429(configured):
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        assert run(rc.search_listings("test")) is None


def test_search_fallback_on_exception(configured):
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        assert run(rc.search_listings("test")) is None


# ── batch_lookup ──

def test_batch_returns_empty_without_key():
    assert run(rc.batch_lookup(["123", "456"])) == {}


def test_batch_success(configured):
    batch_resp = {"data": {"items": [SAMPLE_ITEM, {**SAMPLE_ITEM, "id": "456", "title": "iPad"}]}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = batch_resp

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = run(rc.batch_lookup(["123456789012", "456"]))

    assert "123456789012" in result
    assert "456" in result


# ── get_item_detail ──

def test_detail_returns_none_without_key():
    assert run(rc.get_item_detail("123")) is None


def test_detail_success(configured):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": SAMPLE_ITEM}

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = run(rc.get_item_detail("123456789012"))

    assert result["title"] == "iPhone 15 Pro 256GB"
    assert result["source"] == "rapidapi"


# ── Settings persistence ──

def test_set_and_load_api_key(tmp_path):
    rc.set_api_key("my_secret_key_long_enough")
    assert rc._api_key == "my_secret_key_long_enough"
    settings = rc._load_settings()
    assert settings["key"] == "my_secret_key_long_enough"


def test_set_page_size(tmp_path):
    rc.set_page_size(20)
    assert rc._page_size == 20
    settings = rc._load_settings()
    assert settings["page_size"] == 20


def test_set_page_size_clamped():
    rc.set_page_size(100)
    assert rc._page_size == 30
    rc.set_page_size(0)
    assert rc._page_size == 1


def test_call_counter_increments(tmp_path):
    rc._api_key = "test_key_long_enough_1234567890"
    assert rc._calls_today == 0
    rc._increment_calls()
    assert rc._calls_today == 1
    settings = rc._load_settings()
    assert settings["calls_today"] == 1


def test_init_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "env_key_long_enough_1234567890")
    rc.init_rapidapi()
    assert rc._api_key == "env_key_long_enough_1234567890"
    assert rc.is_configured() is True


def test_init_loads_from_settings_file(tmp_path, monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    rc._save_settings({"key": "file_key_long_enough_1234567890", "calls_today": 5, "calls_date": rc._today()})
    rc.init_rapidapi()
    assert rc._api_key == "file_key_long_enough_1234567890"
    assert rc._calls_today == 5


def test_clear_key():
    rc._api_key = "something"
    rc.set_api_key("")
    assert rc._api_key is None
    assert rc.is_configured() is False


# ── get_status ──

def test_get_status_not_configured():
    status = rc.get_status()
    assert status["active"] is False
    assert status["calls_today"] == 0


def test_get_status_configured(configured):
    rc._calls_today = 7
    status = rc.get_status()
    assert status["active"] is True
    assert status["calls_today"] == 7


# ── .gitignore safety ──

def test_gitignore_includes_env_and_data():
    gitignore_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".gitignore")
    with open(gitignore_path) as f:
        content = f.read()
    assert ".env" in content
    assert "data/" in content
