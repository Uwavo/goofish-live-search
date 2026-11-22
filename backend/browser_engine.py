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
    USER_AGENTS,
)
from backend.normalizer import normalize_listing
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
    try:
        await _page.goto(GOOFISH_BASE, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await _page.wait_for_timeout(3000)
        await _dismiss_overlays(_page)
    except Exception:
        pass
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
            k in data[0] for k in ("itemId", "title", "price", "id")
        ):
            return data
        for item in data:
            found = _find_items_in_data(item, depth + 1)
            if found:
                return found
    elif isinstance(data, dict):
        if "itemId" in data and "title" in data:
            return [data]
        for key in ("resultList", "items", "itemList", "data", "resultValue"):
            if key in data:
                found = _find_items_in_data(data[key], depth + 1)
                if found:
                    return found
        for v in data.values():
            found = _find_items_in_data(v, depth + 1)
            if found:
                return found
    return []


async def hydrate_item(item_id: str) -> dict | None:
    """Visit a single Goofish item page and extract its live details."""
    if not _context:
        raise RuntimeError("Browser not initialized")

    await _warmup_session()
    await rate_limiter.acquire()

    page = await _context.new_page()
    captured: dict | None = None

    async def on_response(response):
        nonlocal captured
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
                for item in items:
                    iid = str(item.get("itemId", item.get("id", "")))
                    if iid == item_id:
                        captured = item
                        return
                if not captured and items:
                    captured = items[0]
        except Exception:
            pass

    page.on("response", on_response)

    try:
        url = f"{GOOFISH_BASE}/item?id={item_id}"
        await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await _dismiss_overlays(page)
        await page.wait_for_timeout(4000)

        if not captured:
            init_data = await page.evaluate(
                "() => typeof window.__INIT_DATA__ !== 'undefined' ? JSON.parse(JSON.stringify(window.__INIT_DATA__)) : null"
            )
            if init_data:
                items = _find_items_in_data(init_data)
                if items:
                    captured = items[0]

        if not captured:
            captured = await _scrape_item_dom(page, item_id)

        rate_limiter.reset()
        if not captured:
            return None
        result = normalize_listing(captured)
        result["status"] = await _detect_sold_status(page, result.get("status", "unknown"))
        return result

    except Exception as exc:
        if "403" in str(exc) or "captcha" in str(exc).lower():
            rate_limiter.back_off()
        raise
    finally:
        await page.close()


async def _scrape_item_dom(page: Page, item_id: str) -> dict | None:
    try:
        return await page.evaluate("""(itemId) => {
            const title = document.querySelector('[class*="title"], h1')?.textContent?.trim() || '';
            if (!title) return null;
            const priceEl = document.querySelector('[class*="price"], [class*="Price"]');
            const price = priceEl?.textContent?.replace(/[^0-9.]/g, '') || '';
            const images = Array.from(document.querySelectorAll(
                '[class*="image"] img, [class*="gallery"] img, [class*="slider"] img, [class*="pic"] img'
            )).map(img => img.src || img.dataset?.src).filter(Boolean);
            const seller = document.querySelector('[class*="seller"], [class*="user"] [class*="name"], [class*="nick"]')?.textContent?.trim() || '';
            const location = document.querySelector('[class*="area"], [class*="location"], [class*="city"]')?.textContent?.trim() || '';
            const desc = document.querySelector('[class*="desc"], [class*="description"]')?.textContent?.trim() || '';
            return {itemId, title, price, images, sellerNick: seller, area: location, desc};
        }""", item_id)
    except Exception:
        return None


async def _detect_sold_status(page: Page, current: str) -> str:
    try:
        text = await page.evaluate("""() => document.body?.innerText?.substring(0, 2000) || ''""")
        lower = text.lower()
        if any(k in lower for k in ("已售出", "卖掉了", "已下架", "该宝贝已下架", "sold out")):
            return "sold"
        if any(k in lower for k in ("我想要", "立即购买", "buy now")):
            return "on_sale"
    except Exception:
        pass
    return current


async def hydrate_items_batch(item_ids: list[str], concurrency: int = 3) -> list[dict]:
    """Hydrate multiple items with limited concurrency."""
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def _hydrate_one(iid: str):
        async with sem:
            try:
                item = await hydrate_item(iid)
                if item:
                    results.append(item)
            except Exception:
                pass

    await asyncio.gather(*[_hydrate_one(iid) for iid in item_ids])
    return results


def get_context() -> BrowserContext | None:
    return _context


async def is_browser_ready() -> bool:
    return _context is not None and _context.browser is not None
