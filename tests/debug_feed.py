"""Debug: capture feed and search API response bodies."""
import asyncio
import os
import sys
import json
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    profile = os.path.join("data", "debug_profile2")
    os.makedirs(profile, exist_ok=True)

    # Try MOBILE viewport + UA to see if mobile web allows unauthenticated search
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-proxy-server"],
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        viewport={"width": 375, "height": 812},
        locale="zh-CN",
        is_mobile=True,
    )
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = await ctx.new_page()

    captured = {}

    async def on_resp(resp):
        url = resp.url
        try:
            if "h5api" in url or "mtop" in url:
                ct = resp.headers.get("content-type", "")
                if "json" in ct or "javascript" in ct:
                    body = await resp.text()
                    if body.startswith(")]}'\n"):
                        body = body[5:]
                    data = json.loads(body)
                    api = data.get("api", "")
                    ret = data.get("ret", [])
                    print(f"  API: {api}  ret={ret}")
                    if "search" in api.lower() and "SUCCESS" in str(ret):
                        captured["search"] = data
                    elif "feed" in api.lower() and "SUCCESS" in str(ret) and "feed" not in captured:
                        captured["feed"] = data
        except Exception:
            pass

    page.on("response", on_resp)

    # Try mobile search URL directly
    print("=== MOBILE WEB SEARCH ===")
    await page.goto("https://www.goofish.com/search?q=手机壳", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(8000)
    print(f"URL: {page.url}")

    # Check for item links
    links = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href*="/item/"]')).slice(0, 5).map(a => ({
            href: a.href, text: a.textContent.trim().substring(0, 60),
        }));
    }""")
    print(f"Item links: {len(links)}")
    for l in links:
        print(f"  {l['href']}  {l['text']}")

    # Dump search API response if captured
    if "search" in captured:
        with open("data/search_response.json", "w", encoding="utf-8") as f:
            json.dump(captured["search"], f, ensure_ascii=False, indent=2)
        print("Saved search API response to data/search_response.json")
        # Find items
        from backend.browser_engine import _find_items_in_data
        items = _find_items_in_data(captured["search"].get("data", {}))
        print(f"Found {len(items)} items in search response")
        for it in items[:3]:
            print(f"  id={it.get('itemId','')} title={str(it.get('title',''))[:50]}")

    if "feed" in captured:
        from backend.browser_engine import _find_items_in_data
        items = _find_items_in_data(captured["feed"].get("data", {}))
        print(f"\nFeed has {len(items)} items")
        for it in items[:3]:
            print(f"  id={it.get('itemId','')} title={str(it.get('title',''))[:50]}")

    await ctx.close()
    await pw.stop()

asyncio.run(main())
