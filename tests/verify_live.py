"""End-to-end verification: discover real Goofish items via Bing search."""
import asyncio
import os
import sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from backend.browser_engine import init_browser, close_browser, get_context
from backend.discovery import discover_items_with_browser
from backend.translator import translate_query


async def main():
    print("1. Initializing browser...")
    await init_browser()
    ctx = get_context()
    if not ctx:
        print("FAIL: No browser context")
        return 1

    try:
        q = "sony camera"
        translated = translate_query(q)
        print(f"2. Searching for: {q} -> {translated}")
        items = await discover_items_with_browser(ctx, translated, original_query=q, max_items=10)
        print(f"   Found {len(items)} items")

        if not items:
            q2 = "手机壳"
            print(f"   Retrying with: {q2}")
            items = await discover_items_with_browser(ctx, q2, max_items=10)
            print(f"   Found {len(items)} items")

        if not items:
            print("FAIL: No items discovered")
            return 1

        print(f"\n3. Results:")
        for i, item in enumerate(items[:5]):
            print(f"   [{i+1}] {item['title'][:60]}")
            print(f"       ID: {item['id']} | Price: {item.get('price')} | URL: {item['url']}")
            if item.get("description"):
                print(f"       Desc: {item['description'][:60]}")

        print(f"\nSUCCESS: Discovered {len(items)} real Goofish items!")
        return 0
    finally:
        await close_browser()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
