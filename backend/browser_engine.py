import asyncio
import json
import random
import re
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

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
_browser: Browser | None = None
_context: BrowserContext | None = None
_warmed_up = False


async def init_browser() -> None:
    global _playwright, _browser, _context
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    _context = await _browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 768},
        locale="zh-CN",
    )
    _context.set_default_timeout(BROWSER_TIMEOUT_MS)
    await _context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )


async def close_browser() -> None:
    global _playwright, _browser, _context, _warmed_up
    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _context = _browser = _playwright = None
    _warmed_up = False


async def _warmup_session() -> None:
    """Visit homepage to establish cookies before searching."""
    global _warmed_up
    if _warmed_up or not _context:
        return
    page = await _context.new_page()
    try:
        await page.goto(GOOFISH_BASE, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await page.wait_for_timeout(3000)
        _warmed_up = True
    finally:
        await page.close()


async def _dismiss_popups(page: Page) -> None:
    selectors = [
        '[class*="login"] [class*="close"]',
        '[class*="modal"] [class*="close"]',
        '[class*="overlay"] [class*="close"]',
        '[class*="dialog"] [class*="close"]',
        ".login-dialog .close-btn",
        '[class*="qr"] [class*="close"]',
        '[class*="havana"] [class*="close"]',
        'iframe[src*="login"]',
    ]
    for sel in selectors:
        try:
            if sel.startswith("iframe"):
                frames = page.frames
                for frame in frames:
                    if "login" in (frame.url or ""):
                        close_btn = frame.locator('[class*="close"]').first
                        if await close_btn.is_visible(timeout=200):
                            await close_btn.click()
                continue
            el = page.locator(sel).first
            if await el.is_visible(timeout=200):
                await el.click()
                await asyncio.sleep(0.3)
        except Exception:
            pass

    # Also try removing login overlay iframes
    try:
        await page.evaluate("""() => {
            document.querySelectorAll('iframe[src*="login"], iframe[src*="passport"]').forEach(el => el.remove());
            document.querySelectorAll('[class*="login-overlay"], [class*="login-mask"], [class*="havana"]').forEach(el => el.remove());
        }""")
    except Exception:
        pass


async def _try_solve_slider(page: Page) -> bool:
    """Attempt to interact with Alibaba NC slider CAPTCHA if present."""
    try:
        slider_sel = '#nc_1_n1z, [class*="nc_1_n1z"], [id*="nc_"][class*="btn"]'
        slider = page.locator(slider_sel).first
        if not await slider.is_visible(timeout=1000):
            return False

        box = await slider.bounding_box()
        if not box:
            return False

        track_sel = '#nc_1__scale_text, [class*="nc-lang-cnt"], [class*="scale_text"]'
        track = page.locator(track_sel).first
        track_box = await track.bounding_box() if await track.is_visible(timeout=500) else None
        slide_distance = (track_box["width"] if track_box else 300) - box["width"]

        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.mouse.down()
        steps = random.randint(20, 35)
        for i in range(steps):
            progress = (i + 1) / steps
            eased = progress * (2 - progress)
            x = box["x"] + box["width"] / 2 + slide_distance * eased
            y = box["y"] + box["height"] / 2 + random.uniform(-2, 2)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.04))
        await page.mouse.up()
        await page.wait_for_timeout(2000)
        return True
    except Exception:
        return False


def _find_items_in_data(data: Any, depth: int = 0) -> list[dict]:
    if depth > 8 or data is None:
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
        for v in data.values():
            found = _find_items_in_data(v, depth + 1)
            if found:
                return found
    return []


async def _scrape_dom_results(page: Page) -> list[dict]:
    """Fallback: scrape visible search results from the rendered DOM."""
    try:
        items = await page.evaluate("""() => {
            const results = [];
            // Try multiple possible selectors for Goofish search result cards
            const cardSelectors = [
                '[class*="feeds-"] [class*="item"]',
                '[class*="searchResult"] [class*="item"]',
                '[class*="card-item"]',
                '[class*="ItemCard"]',
                '[class*="item-card"]',
                'a[href*="/item/"]',
            ];

            let cards = [];
            for (const sel of cardSelectors) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) break;
            }

            // If no cards found via selectors, try finding all links to items
            if (cards.length === 0) {
                cards = document.querySelectorAll('a[href*="/item/"]');
            }

            const seen = new Set();
            for (const card of cards) {
                const link = card.closest('a[href*="/item/"]') || card.querySelector('a[href*="/item/"]') || card;
                const href = link?.href || '';
                const idMatch = href.match(/item\\/([0-9]+)/);
                if (!idMatch || seen.has(idMatch[1])) continue;
                seen.add(idMatch[1]);

                const img = card.querySelector('img');
                const priceEl = card.querySelector('[class*="price"], [class*="Price"]');
                const titleEl = card.querySelector('[class*="title"], [class*="Title"]') || card;

                results.push({
                    itemId: idMatch[1],
                    title: titleEl?.textContent?.trim()?.substring(0, 200) || '',
                    price: priceEl?.textContent?.replace(/[^0-9.]/g, '') || '',
                    images: img ? [img.src] : [],
                    url: href,
                });
            }
            return results;
        }""")
        return items or []
    except Exception:
        return []


async def search_goofish(
    query: str, sort: str = "default", page_num: int = 1
) -> list[dict]:
    if not _context:
        raise RuntimeError("Browser not initialized")

    await _warmup_session()
    await rate_limiter.acquire()

    page = await _context.new_page()
    captured_items: list[dict] = []

    async def on_response(response):
        try:
            url = response.url
            if "h5api" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            body = await response.text()
            data = json.loads(body)
            api = data.get("api", "")
            ret = str(data.get("ret", []))
            if "search" in api.lower() and "SUCCESS" in ret:
                items = _find_items_in_data(data.get("data", {}))
                if items:
                    captured_items.extend(items)
        except Exception:
            pass

    page.on("response", on_response)

    try:
        sort_param = ""
        if sort == "price_asc":
            sort_param = "&sort=price_asc"
        elif sort == "price_desc":
            sort_param = "&sort=price_desc"

        url = f"{GOOFISH_BASE}/search?q={query}{sort_param}"
        await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await _dismiss_popups(page)
        await page.wait_for_timeout(5000)

        # Try slider CAPTCHA if present
        await _try_solve_slider(page)

        # Wait for potential results to load after slider
        await page.wait_for_timeout(3000)

        # Scroll for pagination
        for _ in range(max(0, page_num - 1)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(SCROLL_DELAY_MS)

        # If no API results captured, try DOM scraping
        if not captured_items:
            dom_items = await _scrape_dom_results(page)
            if dom_items:
                captured_items = dom_items

        rate_limiter.reset()
        return normalize_search_results(captured_items)

    except Exception as exc:
        if "403" in str(exc) or "captcha" in str(exc).lower():
            rate_limiter.back_off()
        raise
    finally:
        await page.close()


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
            if "h5api" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            body = await response.text()
            data = json.loads(body)
            ret = str(data.get("ret", []))
            if "SUCCESS" in ret:
                items = _find_items_in_data(data.get("data", {}))
                if items:
                    for item in items:
                        if str(item.get("itemId", item.get("id", ""))) == item_id:
                            captured_detail = item
                            return
                    if not captured_detail and items:
                        captured_detail = items[0]
        except Exception:
            pass

    page.on("response", on_response)

    try:
        url = f"{GOOFISH_BASE}/item/{item_id}"
        await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await _dismiss_popups(page)
        await page.wait_for_timeout(5000)
        await _try_solve_slider(page)
        await page.wait_for_timeout(3000)

        if not captured_detail:
            # Try DOM scraping for item detail
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
    return _browser is not None and _browser.is_connected()
