import re
from typing import Any


def normalize_image_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        url = "https:" + url
    url = re.sub(r"_\d+x\d+[a-zA-Z]*\d*(?=\.(?:jpg|jpeg|png|webp|gif))", "", url)
    return url


def normalize_images(urls: list[str]) -> list[str]:
    return [normalize_image_url(u) for u in urls if u]


def parse_price(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).replace(",", "").replace("¥", "").replace("￥", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def detect_status(raw: Any) -> str:
    if raw is None:
        return "unknown"
    s = str(raw).lower()
    if any(k in s for k in ("sold", "下架", "已卖出")):
        return "sold"
    return "on_sale"


def normalize_listing(raw: dict) -> dict:
    data = raw.get("data", raw)
    images_raw = (
        data.get("images", [])
        or data.get("imageList", [])
        or data.get("picList", [])
    )
    if isinstance(images_raw, list) and images_raw and isinstance(images_raw[0], dict):
        images_raw = [img.get("url", img.get("picUrl", "")) for img in images_raw]

    return {
        "id": str(data.get("itemId", data.get("id", ""))),
        "title": data.get("title", data.get("name", "")),
        "price": parse_price(data.get("price", data.get("soldPrice"))),
        "images": normalize_images(images_raw),
        "seller": data.get("sellerNick", data.get("seller", {}).get("nick", "")),
        "location": data.get("area", data.get("location", "")),
        "status": detect_status(data.get("status", data.get("itemStatus"))),
        "url": f"https://www.goofish.com/item/{data.get('itemId', data.get('id', ''))}",
        "description": data.get("desc", data.get("description", "")),
    }


def normalize_search_results(raw_items: list[dict]) -> list[dict]:
    return [normalize_listing(item) for item in raw_items if item]


def filter_by_price(
    items: list[dict], min_price: float | None, max_price: float | None
) -> list[dict]:
    result = []
    for item in items:
        p = item.get("price")
        if p is None:
            continue
        if min_price is not None and p < min_price:
            continue
        if max_price is not None and p > max_price:
            continue
        result.append(item)
    return result
