"""RapidAPI Goofish/Xianyu client for Guest Mode enrichment."""
import json
import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

RAPIDAPI_HOST = "goofish-xianyu-api-secondhand-deals-and-sellers.p.rapidapi.com"
_api_key: str | None = None
_calls_today: int = 0
_calls_date: str = ""
_page_size: int = 10

SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "rapidapi_settings.json"
)

SORT_MAP = {
    "relevance": "relevance",
    "price_asc": "priceAsc",
    "price_desc": "priceDesc",
    "deal": "priceDrop",
    "newest": "newest",
    "popularity": "popularity",
    "credit": "credit",
    "priceDrop": "priceDrop",
    "priceAsc": "priceAsc",
    "priceDesc": "priceDesc",
}


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def init_rapidapi() -> None:
    global _api_key, _calls_today, _calls_date, _page_size
    key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not key:
        settings = _load_settings()
        key = settings.get("key", "")
    _api_key = key or None
    settings = _load_settings()
    _calls_date = settings.get("calls_date", "")
    if _calls_date == _today():
        _calls_today = settings.get("calls_today", 0)
    else:
        _calls_today = 0
        _calls_date = _today()
    _page_size = settings.get("page_size", 10)
    if _api_key:
        log.info("RapidAPI key loaded (%d calls today, page_size=%d)", _calls_today, _page_size)
    else:
        log.info("RapidAPI key not set — Guest Mode uses Bing only")


def set_api_key(key: str) -> None:
    global _api_key
    _api_key = key.strip() or None
    settings = _load_settings()
    settings["key"] = _api_key or ""
    _save_settings(settings)
    log.info("RapidAPI key %s", "saved" if _api_key else "cleared")


def set_page_size(size: int) -> None:
    global _page_size
    _page_size = max(1, min(size, 30))
    settings = _load_settings()
    settings["page_size"] = _page_size
    _save_settings(settings)


def get_status() -> dict:
    return {
        "active": is_configured(),
        "calls_today": _calls_today,
        "date": _calls_date or _today(),
        "page_size": _page_size,
    }


def _increment_calls() -> None:
    global _calls_today, _calls_date
    today = _today()
    if _calls_date != today:
        _calls_today = 0
        _calls_date = today
    _calls_today += 1
    settings = _load_settings()
    settings["calls_today"] = _calls_today
    settings["calls_date"] = _calls_date
    _save_settings(settings)


def is_configured() -> bool:
    return _api_key is not None and len(_api_key) > 10


def _headers() -> dict:
    return {
        "X-RapidAPI-Key": _api_key or "",
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }


async def search_listings(
    keyword: str,
    *,
    page: int = 1,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str = "relevance",
    personal_only: bool = False,
    free_shipping: bool = False,
    brand_new: bool = False,
    inspected_only: bool = False,
    publish_days: int | None = None,
    region: str | None = None,
) -> list[dict] | None:
    if not is_configured():
        return None
    params: dict = {"keyword": keyword, "page": str(page), "page_size": str(_page_size)}
    if min_price is not None:
        params["price_min"] = str(min_price)
    if max_price is not None:
        params["price_max"] = str(max_price)
    params["sort_by"] = SORT_MAP.get(sort, "relevance")
    if personal_only:
        params["personal_only"] = "true"
    if free_shipping:
        params["free_shipping"] = "true"
    if brand_new:
        params["brand_new"] = "true"
    if inspected_only:
        params["inspected_only"] = "true"
    if publish_days:
        params["publish_days"] = str(publish_days)
    if region:
        params["region"] = region
    params["no_cache"] = "false"

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                f"https://{RAPIDAPI_HOST}/v1/goofish/search",
                params=params,
                headers=_headers(),
            )
        if resp.status_code in (401, 403, 429):
            log.warning("RapidAPI search: HTTP %d — falling back", resp.status_code)
            return None
        if resp.status_code == 200:
            _increment_calls()
            data = resp.json()
            items_raw = data.get("data", data.get("items", data.get("results", [])))
            if isinstance(items_raw, dict):
                items_raw = items_raw.get("items", items_raw.get("results", []))
            if not isinstance(items_raw, list):
                items_raw = []
            return [normalize_item(it) for it in items_raw]
        log.warning("RapidAPI search: HTTP %d", resp.status_code)
        return None
    except Exception as e:
        log.warning("RapidAPI search error: %s", e)
        return None


async def get_item_detail(item_id: str) -> dict | None:
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://{RAPIDAPI_HOST}/v1/goofish/item",
                params={"item_id": item_id},
                headers=_headers(),
            )
        if resp.status_code == 200:
            _increment_calls()
            raw = resp.json()
            return normalize_item(raw.get("data", raw))
        log.warning("RapidAPI item detail %s: HTTP %d", item_id, resp.status_code)
        return None
    except Exception as e:
        log.warning("RapidAPI item detail error: %s", e)
        return None


async def batch_lookup(item_ids: list[str]) -> dict[str, dict]:
    if not is_configured() or not item_ids:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://{RAPIDAPI_HOST}/v1/goofish/items/batch",
                json={"item_ids": item_ids, "no_cache": False},
                headers={**_headers(), "Content-Type": "application/json"},
            )
        if resp.status_code == 200:
            _increment_calls()
            data = resp.json()
            outer = data.get("data", data)
            items_raw = outer.get("items", outer) if isinstance(outer, dict) else outer
            if isinstance(items_raw, list):
                return {str(_extract_id(it)): normalize_item(it) for it in items_raw}
            if isinstance(items_raw, dict):
                return {k: normalize_item(v) for k, v in items_raw.items()}
        log.warning("RapidAPI batch: HTTP %d", resp.status_code)
        return {}
    except Exception as e:
        log.warning("RapidAPI batch error: %s", e)
        return {}


def _extract_id(raw: dict) -> str:
    return str(raw.get("item_id", raw.get("itemId", raw.get("id", ""))))


def normalize_item(raw: dict) -> dict:
    data = raw.get("data", raw) if isinstance(raw, dict) else raw

    images = (
        data.get("imageUrls")
        or data.get("images")
        or data.get("imageList")
        or data.get("picList")
        or data.get("pics")
        or []
    )
    if isinstance(images, list) and images:
        if isinstance(images[0], dict):
            images = [img.get("url", img.get("picUrl", "")) for img in images]
        images = [("https:" + u if u.startswith("//") else u) for u in images if u]

    price = data.get("price", data.get("soldPrice", data.get("originalPrice")))
    if isinstance(price, str):
        try:
            price = float(price.replace(",", "").replace("¥", "").replace("￥", "").strip())
        except ValueError:
            price = None
    elif isinstance(price, (int, float)):
        price = float(price)
    else:
        price = None

    status_raw = str(data.get("status", data.get("itemStatus", ""))).lower()
    status = "sold" if any(k in status_raw for k in ("sold", "下架", "已卖出")) else "on_sale"

    item_id = _extract_id(data)

    seller_raw = data.get("seller", data.get("sellerInfo", {}))
    if isinstance(seller_raw, dict):
        seller = seller_raw.get("nick", seller_raw.get("nickname", seller_raw.get("sellerNick", "")))
        location = seller_raw.get("area", seller_raw.get("location", data.get("city", data.get("area", data.get("location", "")))))
    else:
        seller = str(seller_raw) if seller_raw else data.get("sellerNick", "")
        location = data.get("city", data.get("area", data.get("location", "")))

    condition = data.get("condition", "")
    specs = data.get("specs", {})

    result = {
        "id": item_id,
        "title": data.get("title", data.get("name", "")),
        "price": price,
        "images": images,
        "seller": seller,
        "location": location,
        "status": status,
        "url": f"https://www.goofish.com/item?id={item_id}" if item_id else "",
        "description": data.get("desc", data.get("description", data.get("content", ""))),
        "source": "rapidapi",
    }
    if condition:
        result["condition"] = condition
    if specs:
        result["specs"] = specs
    return result
