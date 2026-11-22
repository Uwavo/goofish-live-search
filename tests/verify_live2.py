"""Verify: direct test of the engine flow with logging."""
import asyncio
import os
import sys
import json
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from playwright.async_api import async_playwright
from backend.browser_engine import _extract_feed_items, _find_items_in_data
from backend.normalizer import normalize_search_results


async def main():
    pw = await async_playwright().start()
    profile = os.path.join("data", "verify_profile")
    os.makedirs(profile, exist_ok=True)

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=profile, headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-proxy-server"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768}, locale="zh-CN",
        ignore_default_args=["--enable-automation"],
    )
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = await ctx.new_page()

    # Warmup
    print("1. Warming up on homepage...")
    await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(4000)
    await page.evaluate("""() => {
        document.querySelectorAll('iframe, [class*="login"], [class*="modal"]').forEach(el => el.remove());
    }""")

    # Now attach listener and search
    captured_search = []
    feed_items = []

    async def on_resp(resp):
        try:
            url = resp.url
            if "h5api" not in url and "mtop" not in url:
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await resp.text()
            if body.startswith(")]}'\n"):
                body = body[5:]
            data = json.loads(body)
            api = str(data.get("api", ""))
            ret = str(data.get("ret", []))
            print(f"  >> {api}  SUCCESS={'SUCCESS' in ret}")
            if "SUCCESS" in ret:
                if "search" in api.lower() and "suggest" not in api and "shade" not in api and "activate" not in api:
                    items = _find_items_in_data(data.get("data", {}))
                    print(f"     search items: {len(items)}")
                    captured_search.extend(items)
                elif "feed" in api.lower():
                    fi = _extract_feed_items(data)
                    print(f"     feed items: {len(fi)}")
                    feed_items.extend(fi)
        except Exception as e:
            print(f"  >> error: {e}")

    page.on("response", on_resp)

    print("2. Typing search query...")
    inp = page.locator('input[class*="search-input"]').first
    visible = await inp.is_visible(timeout=2000)
    print(f"   search-input visible: {visible}")
    if not visible:
        inp = page.locator("input").first
        print(f"   fallback to first input")
    await inp.click()
    await inp.fill("")
    await inp.type("耳机", delay=80)
    await asyncio.sleep(0.5)
    await inp.press("Enter")

    print("3. Waiting for responses...")
    await page.wait_for_timeout(8000)
    print(f"   URL: {page.url}")
    print(f"   Search items: {len(captured_search)}, Feed items: {len(feed_items)}")

    all_items = captured_search if captured_search else feed_items
    results = normalize_search_results(all_items)
    print(f"\n4. Normalized results: {len(results)}")
    for i, item in enumerate(results[:5]):
        print(f"  [{i+1}] {item.get('title','')[:50]}  price={item.get('price')}  id={item.get('id')}")

    await ctx.close()
    await pw.stop()
    return 0 if results else 1

sys.exit(asyncio.run(main()))
