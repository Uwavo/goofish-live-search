import asyncio
import json
import os
import random
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

from backend.config import (
    BROWSER_TIMEOUT_MS,
    GOOFISH_BASE,
    NAVIGATION_TIMEOUT_MS,
    SCROLL_DELAY_MS,
    USER_AGENTS,
)
from backend.normalizer import normalize_listing, normalize_search_results
from backend.rate_limiter import rate_limiter

_playwright = None
_context: BrowserContext | None = None
_page: Page | None = None
_warmed_up = False

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "browser_profile")


async def init_browser() -> None:
    global _playwright, _context, _page, _warmed_up
    os.makedirs(PROFILE_DIR, exist_ok=True)
    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--no-proxy-server",
        ],
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 768},
        locale="zh-CN",
        ignore_default_args=["--enable-automation"],
    )
    _context.set_default_timeout(BROWSER_TIMEOUT_MS)
    await _context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    _page = await _context.new_page()
    await _warmup_session()


async def close_browser() -> None:
    global _playwright, _context, _page, _warmed_up
    if _context:
        await _context.close()
    if _playwright:
        await _playwright.stop()
    _context = _page = _playwright = None
    _warmed_up = False


async def _warmup_session() -> None:
    global _warmed_up
    if _warmed_up or not _page:
        return
    await _page.goto(GOOFISH_BASE, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    await _page.wait_for_timeout(4000)
    await _dismiss_overlays(_page)
    _warmed_up = True


async def _dismiss_overlays(page: Page) -> None:
    try:
        await page.evaluate("""() => {
            const sels = [
                'iframe[src*="login"]', 'iframe[src*="passport"]', 'iframe[src*="havana"]',
                '[class*="login-overlay"]', '[class*="login-mask"]', '[class*="havana"]',
                '[class*="modal-mask"]', '[class*="login-dialog"]', '[class*="qrcode"]',
                '[class*="guide-dialog"]',
            ];
            sels.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
        }""")
    except Exception:
        pass


def _find_items_in_data(data: Any, depth: int = 0) -> list[dict]:
    if depth > 10 or data is None:
        return []
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and any(
            k in data[0] for k in ("itemId", "title", "price", "id", "item2")
        ):
            return data
        for item in data:
            found = _find_items_in_data(item, depth + 1)
            if found:
                return found
    elif isinstance(data, dict):
        if "itemId" in data and "title" in data:
            return [data]
        for key in ("resultList", "items", "itemList", "pcSearchResult", "data", "resultValue"):
            if key in data:
                found = _find_items_in_data(data[key], depth + 1)
                if found:
                    return found
        for v in data.values():
            found = _find_items_in_data(v, depth + 1)
            if found:
                return found
    return []


def _extract_feed_items(data: dict) -> list[dict]:
    """Extract items from the feed API cardList structure."""
    items = []
    cards = data.get("data", {}).get("cardList", [])
    for card in cards:
        cd = card.get("cardData", {})
        dp = cd.get("detailParams", {})
        item_id = dp.get("itemId", "")
        if not item_id:
            continue
        images_raw = []
        pic = dp.get("picUrl", "")
        if pic:
            images_raw.append(pic)
        items.append({
            "itemId": item_id,
            "title": dp.get("title", ""),
            "price": dp.get("soldPrice", cd.get("soldPrice", "")),
            "images": images_raw,
            "sellerNick": dp.get("userNick", ""),
            "area": cd.get("city", ""),
            "url": f"https://www.goofish.com/item/{item_id}",
        })
    return items


async def _type_search(page: Page, query: str) -> None:
    """Type query into the real search input and press Enter."""
    input_sels = [
        'input[class*="search-input"]',
        'input[placeholder*="搜索"]', 'input[placeholder*="search"]',
        '#search-input', 'input[name="q"]', 'input[type="search"]',
        '[class*="search"] input', '[class*="Search"] input',
    ]
    for sel in input_sels:
        try:
            inp = page.locator(sel).first
            if await inp.is_visible(timeout=1500):
                await inp.click()
                await inp.fill("")
                await asyncio.sleep(0.3)
                await inp.type(query, delay=random.randint(50, 120))
                await asyncio.sleep(0.3)
                await inp.press("Enter")
                return
        except Exception:
            continue
    await page.goto(f"{GOOFISH_BASE}/search?q={query}", wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)


async def search_goofish(
    query: str, sort: str = "default", page_num: int = 1
) -> list[dict]:
    if not _context or not _page:
        raise RuntimeError("Browser not initialized")

    await _warmup_session()
    await rate_limiter.acquire()

    page = _page
    captured_items: list[dict] = []
    feed_items: list[dict] = []

    async def on_response(response):
        try:
            url = response.url
            if "h5api" not in url and "mtop" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await response.text()
            if body.startswith(")]}'\n"):
                body = body[5:]
            data = json.loads(body)
            api = str(data.get("api", ""))
            ret = str(data.get("ret", []))

            if "SUCCESS" in ret:
                if "search" in api.lower() and "suggest" not in api.lower() and "shade" not in api.lower() and "activate" not in api.lower():
                    items = _find_items_in_data(data.get("data", {}))
                    if items:
                        captured_items.extend(items)
                elif "feed" in api.lower():
                    feed_items.extend(_extract_feed_items(data))
        except Exception:
            pass

    page.on("response", on_response)

    try:
        await _type_search(page, query)
        await _dismiss_overlays(page)
        await page.wait_for_timeout(6000)

        for _ in range(max(0, page_num - 1)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(SCROLL_DELAY_MS)

        if captured_items:
            rate_limiter.reset()
            return {"source": "search", "items": normalize_search_results(captured_items)}

        if feed_items:
            rate_limiter.reset()
            return {"source": "feed", "items": normalize_search_results(feed_items)}

        rate_limiter.reset()
        return {"source": "none", "items": []}

    except Exception as exc:
        if "403" in str(exc) or "captcha" in str(exc).lower():
            rate_limiter.back_off()
        raise
    finally:
        page.remove_listener("response", on_response)


def _filter_feed_by_query(items: list[dict], query: str) -> list[dict]:
    """Best-effort filter: keep items whose title contains any query character sequence."""
    chars = list(query.lower())
    filtered = []
    for item in items:
        title = str(item.get("title", "")).lower()
        if any(c in title for c in chars if c.strip()):
            filtered.append(item)
    return filtered


async def get_item_detail(item_id: str) -> dict | None:
    if not _context:
        raise RuntimeError("Browser not initialized")

    await _warmup_session()
    await rate_limiter.acquire()

    page = await _context.new_page()
    captured_detail: dict | None = None

    async def on_response(response):
        nonlocal captured_detail
        try:
            url = response.url
            if "h5api" not in url and "mtop" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await response.text()
            if body.startswith(")]}'\n"):
                body = body[5:]
            data = json.loads(body)
            ret = str(data.get("ret", []))
            if "SUCCESS" in ret:
                items = _find_items_in_data(data.get("data", {}))
                if items:
                    for item in items:
                        if str(item.get("itemId", item.get("id", ""))) == item_id:
                            captured_detail = item
                            return
                    if not captured_detail:
                        captured_detail = items[0]
        except Exception:
            pass

    page.on("response", on_response)

    try:
        url = f"{GOOFISH_BASE}/item/{item_id}"
        await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await _dismiss_overlays(page)
        await page.wait_for_timeout(5000)

        if not captured_detail:
            init_data = await page.evaluate(
                "() => typeof window.__INIT_DATA__ !== 'undefined' ? JSON.parse(JSON.stringify(window.__INIT_DATA__)) : null"
            )
            if init_data:
                items = _find_items_in_data(init_data)
                if items:
                    captured_detail = items[0]

        if not captured_detail:
            detail = await page.evaluate("""() => {
                const title = document.querySelector('[class*="title"], h1')?.textContent?.trim() || '';
                const price = document.querySelector('[class*="price"], [class*="Price"]')?.textContent?.replace(/[^0-9.]/g, '') || '';
                const images = Array.from(document.querySelectorAll('[class*="image"] img, [class*="gallery"] img, [class*="slider"] img'))
                    .map(img => img.src).filter(Boolean);
                const seller = document.querySelector('[class*="seller"], [class*="user"] [class*="name"]')?.textContent?.trim() || '';
                const location = document.querySelector('[class*="area"], [class*="location"]')?.textContent?.trim() || '';
                const desc = document.querySelector('[class*="desc"], [class*="description"]')?.textContent?.trim() || '';
                if (!title) return null;
                return {title, price, images, seller, location, desc};
            }""")
            if detail:
                detail["itemId"] = item_id
                captured_detail = detail

        rate_limiter.reset()
        return normalize_listing(captured_detail) if captured_detail else None

    except Exception as exc:
        if "403" in str(exc) or "captcha" in str(exc).lower():
            rate_limiter.back_off()
        raise
    finally:
        await page.close()


async def is_browser_ready() -> bool:
    return _context is not None and _context.browser is not None
