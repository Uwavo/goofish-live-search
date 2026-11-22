import asyncio
import json
import logging
import os
import random
import time
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

from backend.config import (
    BROWSER_TIMEOUT_MS,
    COOLDOWN_SECONDS,
    GOOFISH_BASE,
    NAVIGATION_TIMEOUT_MS,
    REQUEST_JITTER_MAX,
    REQUEST_JITTER_MIN,
    SESSION_STATE_PATH,
    SPAM_KEYWORDS,
    USER_AGENTS,
)
from backend.normalizer import normalize_listing

log = logging.getLogger(__name__)

_playwright = None
_context: BrowserContext | None = None
_warmed_up = False
_cooldown_until = 0.0

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "browser_profile")


def _session_exists() -> bool:
    return os.path.isfile(SESSION_STATE_PATH)


async def init_browser() -> None:
    global _playwright, _context, _warmed_up
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SESSION_STATE_PATH), exist_ok=True)
    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=True,
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
    if _session_exists():
        await _load_session_cookies()
    _warmed_up = False


async def close_browser() -> None:
    global _playwright, _context, _warmed_up
    if _context:
        await _context.close()
    if _playwright:
        await _playwright.stop()
    _context = _playwright = None
    _warmed_up = False


async def _load_session_cookies() -> None:
    if not _context or not _session_exists():
        return
    try:
        with open(SESSION_STATE_PATH, "r") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        if cookies:
            await _context.add_cookies(cookies)
            log.info("Loaded %d session cookies", len(cookies))
    except Exception as e:
        log.warning("Failed to load session: %s", e)


async def save_session() -> None:
    if not _context:
        return
    try:
        state = await _context.storage_state()
        os.makedirs(os.path.dirname(SESSION_STATE_PATH), exist_ok=True)
        with open(SESSION_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        log.info("Session saved")
    except Exception as e:
        log.warning("Failed to save session: %s", e)


async def clear_session() -> None:
    if os.path.isfile(SESSION_STATE_PATH):
        os.remove(SESSION_STATE_PATH)
    if _context:
        await _context.clear_cookies()
    log.info("Session cleared")


def get_session_status() -> str:
    if not _session_exists():
        return "guest"
    try:
        with open(SESSION_STATE_PATH, "r") as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        auth_cookies = [c for c in cookies if c.get("name") in ("cookie2", "unb", "_m_h5_tk")]
        return "connected" if auth_cookies else "guest"
    except Exception:
        return "guest"


async def _jitter() -> None:
    delay = random.uniform(REQUEST_JITTER_MIN, REQUEST_JITTER_MAX)
    await asyncio.sleep(delay)


def _check_cooldown() -> bool:
    return time.time() < _cooldown_until


def _enter_cooldown() -> None:
    global _cooldown_until
    _cooldown_until = time.time() + COOLDOWN_SECONDS
    log.warning("Entering cooldown for %ds", COOLDOWN_SECONDS)


async def _warmup_session() -> None:
    global _warmed_up
    if _warmed_up or not _context:
        return
    page = await _context.new_page()
    try:
        await page.goto(GOOFISH_BASE, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await page.wait_for_timeout(2000)
    except Exception:
        pass
    finally:
        await page.close()
    _warmed_up = True


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


async def search_authenticated(query: str, max_items: int = 20) -> list[dict] | None:
    """Search Goofish using authenticated session. Returns None if session is invalid."""
    if not _context or get_session_status() != "connected":
        return None
    if _check_cooldown():
        return None

    await _warmup_session()
    await _jitter()

    page = await _context.new_page()
    captured_items = []

    async def on_response(response):
        try:
            url = response.url
            if "mtop" not in url and "h5api" not in url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await response.text()
            if body.startswith(")]}'\n"):
                body = body[5:]
            data = json.loads(body)
            ret_list = data.get("ret", [])
            ret_str = str(ret_list)

            if "SESSION_EXPIRED" in ret_str:
                log.warning("Session expired")
                return

            if "SUCCESS" in ret_str:
                items = _find_items_in_data(data.get("data", {}))
                for item in items:
                    captured_items.append(item)
        except Exception:
            pass

    page.on("response", on_response)

    try:
        from urllib.parse import quote_plus
        search_url = f"{GOOFISH_BASE}/search?q={quote_plus(query)}"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        await page.wait_for_timeout(5000)

        if not captured_items:
            return None

        results = []
        seen = set()
        for raw in captured_items[:max_items]:
            item = normalize_listing(raw)
            iid = item.get("id", "")
            if iid and iid not in seen:
                seen.add(iid)
                title_lower = item.get("title", "").lower()
                if not any(kw in title_lower for kw in SPAM_KEYWORDS):
                    item["source"] = "goofish_live"
                    results.append(item)

        return results if results else None

    except Exception as exc:
        if "403" in str(exc) or "captcha" in str(exc).lower():
            _enter_cooldown()
        return None
    finally:
        await page.close()


async def open_login_window() -> dict:
    """Open a VISIBLE browser window for Alipay QR login. Returns status."""
    if not _playwright:
        return {"success": False, "error": "Browser not initialized"}

    login_ctx = await _playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-proxy-server",
        ],
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 500, "height": 700},
        locale="zh-CN",
        ignore_default_args=["--enable-automation"],
    )

    page = await login_ctx.new_page()
    try:
        await page.goto(f"{GOOFISH_BASE}/login", wait_until="domcontentloaded", timeout=30000)

        for _ in range(120):
            await page.wait_for_timeout(1000)
            cookies = await login_ctx.cookies()
            auth = [c for c in cookies if c.get("name") in ("cookie2", "unb")]
            if auth:
                state = await login_ctx.storage_state()
                os.makedirs(os.path.dirname(SESSION_STATE_PATH), exist_ok=True)
                with open(SESSION_STATE_PATH, "w") as f:
                    json.dump(state, f, indent=2)
                if _context:
                    await _context.add_cookies(cookies)
                await login_ctx.close()
                return {"success": True, "status": "connected"}

        await login_ctx.close()
        return {"success": False, "error": "Login timed out (2 minutes)"}
    except Exception as e:
        try:
            await login_ctx.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def get_context() -> BrowserContext | None:
    return _context


async def is_browser_ready() -> bool:
    return _context is not None
