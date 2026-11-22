"""Debug: check what the search page DOM actually contains after navigation."""
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

    feed_items = []

    async def on_resp(resp):
        url = resp.url
        try:
            if ("h5api" in url or "mtop" in url):
                ct = resp.headers.get("content-type", "")
                if "json" in ct or "javascript" in ct:
                    body = await resp.text()
                    if body.startswith(")]}'\n"):
                        body = body[5:]
                    data = json.loads(body)
                    api = data.get("api", "")
                    ret = data.get("ret", [])
                    if "feed" in api and "SUCCESS" in str(ret):
                        cards = data.get("data", {}).get("cardList", [])
                        for card in cards:
                            cd = card.get("cardData", {})
                            dp = cd.get("detailParams", {})
                            if dp.get("itemId"):
                                feed_items.append({
                                    "itemId": dp["itemId"],
                                    "title": dp.get("title", ""),
                                    "price": dp.get("soldPrice", ""),
                                    "picUrl": dp.get("picUrl", ""),
                                    "userNick": dp.get("userNick", ""),
                                    "city": cd.get("city", ""),
                                })
        except Exception:
            pass

    page.on("response", on_resp)

    # Warmup
    print("1. Homepage warmup (desktop)...")
    await page.goto("https://www.goofish.com", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(5000)
    await page.evaluate("""() => {
        document.querySelectorAll('iframe, [class*="login"], [class*="modal"], [class*="overlay"]').forEach(el => el.remove());
    }""")
    print(f"   Feed items from homepage: {len(feed_items)}")

    # Type search
    feed_items.clear()
    print("\n2. Typing search...")
    inp = page.locator("input").first
    await inp.click()
    await inp.fill("")
    await inp.type("手机壳", delay=80)
    await asyncio.sleep(0.5)
    await inp.press("Enter")
    await page.wait_for_timeout(10000)

    print(f"   URL: {page.url}")
    print(f"   Feed items from search page: {len(feed_items)}")
    for it in feed_items[:5]:
        print(f"   [{it['itemId']}] {it['title'][:50]}  ¥{it['price']}  {it['city']}")

    # Check DOM content
    print("\n3. DOM analysis...")
    dom_info = await page.evaluate("""() => {
        const links = document.querySelectorAll('a[href*="/item/"]');
        const imgs = document.querySelectorAll('img[src*="alicdn"]');
        const cards = document.querySelectorAll('[class*="card"], [class*="Card"]');
        const feedEls = document.querySelectorAll('[class*="feed"], [class*="Feed"]');
        return {
            itemLinks: links.length,
            alicdnImgs: imgs.length,
            cards: cards.length,
            feedEls: feedEls.length,
            bodyText: document.body?.innerText?.substring(0, 500) || '',
        };
    }""")
    print(f"   Item links: {dom_info['itemLinks']}")
    print(f"   alicdn imgs: {dom_info['alicdnImgs']}")
    print(f"   cards: {dom_info['cards']}")
    print(f"   feed elements: {dom_info['feedEls']}")
    print(f"   Body text preview: {dom_info['bodyText'][:300]}")

    # Scroll and wait for more feed
    print("\n4. Scrolling for more...")
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(3000)
    print(f"   Total feed items: {len(feed_items)}")

    await ctx.close()
    await pw.stop()

asyncio.run(main())
