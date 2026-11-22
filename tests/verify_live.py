"""Standalone verification: does a real Goofish search return items?"""
import asyncio
import os
import sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from backend.browser_engine import init_browser, close_browser, search_goofish


async def main():
    print("Initializing browser with persistent profile...")
    await init_browser()
    try:
        query = "手机壳"
        print(f"Searching for: {query}")
        results = await search_goofish(query)
        print(f"Got {len(results)} results")
        ok = False
        for i, item in enumerate(results[:5]):
            title = item.get("title", "???")[:60]
            price = item.get("price", "?")
            imgs = len(item.get("images", []))
            iid = item.get("id", "")
            print(f"  [{i+1}] {title}  price={price}  images={imgs}  id={iid}")
            if iid and title:
                ok = True
        if ok:
            print("\nSUCCESS: Live search returned real items with IDs and titles.")
            return 0
        else:
            print("\nFAILED: No valid items returned.")
            return 1
    finally:
        await close_browser()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
