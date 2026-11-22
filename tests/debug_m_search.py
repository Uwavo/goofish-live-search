"""Debug: try m.goofish.com (mobile H5) which may allow unauthenticated search."""
import asyncio
import os
import sys
import json
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    profile = os.path.join("data", "debug_mobile")
    os.makedirs(profile, exist_ok=True)

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

    captured_search = []

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
                    print(f"  API: {api}  ret={str(ret)[:80]}")
                    if "search" in api.lower() and "SUCCESS" in str(ret):
                        captured_search.append(data)
        except Exception:
            pass

    page.on("response", on_resp)

    # Warmup on homepage first
    print("1. Homepage warmup (mobile)...")
    await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(5000)

    # Remove overlays
    await page.evaluate("""() => {
        document.querySelectorAll('iframe, [class*="login"], [class*="modal"], [class*="overlay"]').forEach(el => el.remove());
    }""")

    print(f"   URL after warmup: {page.url}")

    # Now try navigating to search - maybe with mobile it works
    print("2. Direct search navigation (mobile)...")
    await page.goto("https://www.goofish.com/search?q=手机壳", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(8000)
    print(f"   URL: {page.url}")

    # Check DOM items
    links = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href*="/item/"]')).slice(0, 5).map(a => ({
            href: a.href, text: a.textContent.trim().substring(0, 60),
        }));
    }""")
    print(f"   Item links: {len(links)}")

    # Also try m.goofish.com directly
    print("3. Trying m.goofish.com...")
    await page.goto("https://m.goofish.com/search?q=手机壳", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(8000)
    print(f"   URL: {page.url}")

    # Check for search results captured
    print(f"\n4. Total search API successes: {len(captured_search)}")
    if captured_search:
        d = captured_search[0].get("data", {})
        print("   Keys:", list(d.keys())[:10])

    await ctx.close()
    await pw.stop()

asyncio.run(main())
