import pytest
import pytest_asyncio

from playwright.async_api import async_playwright

from backend.normalizer import normalize_search_results, normalize_listing

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

SEARCH_URL = "https://www.goofish.com/search?q={query}"


@pytest_asyncio.fixture
async def page():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = await browser.new_context(locale="zh-CN", viewport={"width": 1366, "height": 768})
    p = await ctx.new_page()
    yield p
    await ctx.close()
    await browser.close()
    await pw.stop()


async def _search(page, query):
    import json, re
    captured = []

    async def on_resp(resp):
        try:
            url = resp.url
            if not any(k in url for k in ("/search", "/mtop.", "searchItems")):
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await resp.text()
            if body.startswith(")]}'\n"):
                body = body[5:]
            m = re.search(r"\{.*\}", body, re.DOTALL)
            if m:
                data = json.loads(m.group())
                from backend.browser_engine import _find_items_in_data
                items = _find_items_in_data(data)
                if items:
                    captured.extend(items)
        except Exception:
            pass

    page.on("response", on_resp)
    await page.goto(SEARCH_URL.format(query=query), wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(3000)

    if not captured:
        init = await page.evaluate(
            "() => typeof __INIT_DATA__ !== 'undefined' ? JSON.parse(JSON.stringify(__INIT_DATA__)) : null"
        )
        if init:
            from backend.browser_engine import _find_items_in_data
            captured = _find_items_in_data(init)

    return normalize_search_results(captured)


async def test_live_search(page):
    results = await _search(page, "手机壳")
    assert isinstance(results, list)
    assert len(results) > 0
    item = results[0]
    assert item.get("id")
    assert item.get("title")


async def test_live_search_has_images(page):
    results = await _search(page, "耳机")
    has_images = any(item.get("images") for item in results)
    assert has_images
