"""Debug: capture ALL successful API response bodies to find item data."""
import asyncio
import os
import sys
import json
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    profile = os.path.join("data", "debug_profile3")
    os.makedirs(profile, exist_ok=True)

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-proxy-server"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="zh-CN",
    )
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = await ctx.new_page()

    os.makedirs("data/api_dumps", exist_ok=True)
    counter = [0]

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
                    api = data.get("api", "?")
                    ret = data.get("ret", [])
                    counter[0] += 1
                    fname = f"data/api_dumps/{counter[0]:03d}_{api.replace('.','_')}.json"
                    with open(fname, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    has_items = "item" in json.dumps(data.get("data", {}), ensure_ascii=False)[:500].lower()
                    print(f"  [{counter[0]}] {api}  ret={str(ret)[:60]}  hasItemData={has_items}")
        except Exception as e:
            pass

    page.on("response", on_resp)

    print("1. Homepage warmup...")
    await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(5000)
    await page.evaluate("""() => {
        document.querySelectorAll('iframe, [class*="login"], [class*="modal"], [class*="overlay"]').forEach(el => el.remove());
    }""")

    print("\n2. Typing search...")
    inp = page.locator("input").first
    await inp.click()
    await inp.fill("")
    await inp.type("手机壳", delay=80)
    await asyncio.sleep(0.5)
    await inp.press("Enter")
    await page.wait_for_timeout(10000)

    print(f"\n3. Final URL: {page.url}")
    print(f"   Total API calls: {counter[0]}")
    print(f"   Dumped to data/api_dumps/")

    await ctx.close()
    await pw.stop()

asyncio.run(main())
