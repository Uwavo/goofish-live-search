"""Debug: what's on the goofish page after warmup?"""
import asyncio
import os
import sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from playwright.async_api import async_playwright
import json


async def main():
    pw = await async_playwright().start()
    profile = os.path.join("data", "debug_profile")
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

    captured = []

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
                    captured.append({"api": api, "ret": ret, "url": url[:120]})
                    print(f"  INTERCEPTED: api={api} ret={ret}")
        except Exception:
            pass

    page.on("response", on_resp)

    print("1. Navigating to goofish.com...")
    await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(4000)

    # Remove overlays
    await page.evaluate("""() => {
        document.querySelectorAll('iframe[src*="login"], iframe[src*="passport"], [class*="login"], [class*="modal-mask"], [class*="havana"], [class*="overlay"]').forEach(el => el.remove());
    }""")

    print("2. Looking for search input...")
    inputs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input')).map(el => ({
            id: el.id, name: el.name, type: el.type,
            placeholder: el.placeholder,
            className: el.className.substring(0, 80),
            visible: el.offsetParent !== null,
        }));
    }""")
    for inp in inputs:
        print(f"   INPUT: id={inp['id']} name={inp['name']} placeholder={inp['placeholder']} visible={inp['visible']} class={inp['className']}")

    print("3. Current URL:", page.url)

    # Try typing in first visible input
    for inp in inputs:
        if inp['visible'] and ('search' in inp.get('placeholder', '').lower() or 'search' in inp.get('className', '').lower() or '搜索' in inp.get('placeholder', '')):
            sel = f"#{inp['id']}" if inp['id'] else f"input[placeholder*=\"{inp['placeholder'][:10]}\"]"
            print(f"4. Typing into: {sel}")
            el = page.locator(sel).first
            await el.click()
            await el.fill("")
            await el.type("手机壳", delay=80)
            await asyncio.sleep(0.5)
            await el.press("Enter")
            break
    else:
        print("4. No search input found! Navigating directly...")
        await page.goto("https://www.goofish.com/search?q=手机壳", wait_until="domcontentloaded", timeout=20000)

    print("5. Waiting for results...")
    await page.wait_for_timeout(8000)
    print("6. Current URL:", page.url)

    print(f"7. Intercepted {len(captured)} API calls:")
    for c in captured:
        print(f"   api={c['api']} ret={c['ret']}")

    # Check DOM for item links
    links = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href*="/item/"]')).slice(0, 10).map(a => ({
            href: a.href,
            text: a.textContent.trim().substring(0, 60),
        }));
    }""")
    print(f"8. Item links on page: {len(links)}")
    for l in links:
        print(f"   {l['href']}  text={l['text']}")

    await ctx.close()
    await pw.stop()

asyncio.run(main())
