"""Discover Goofish items via Bing search and extract metadata."""
import asyncio
import logging
import re
from urllib.parse import quote_plus

log = logging.getLogger(__name__)

GOOFISH_ID_RE = re.compile(r"goofish\.com/item[/?](?:id=)?(\d{10,})")

# Matches: ¥1200, ￥1,200.00, 1200元, 售价1200, 出1200, 价格1200, 标价1200
PRICE_RE = re.compile(
    r"(?:[¥￥]\s*(\d[\d,]*(?:\.\d{1,2})?)"       # ¥1200 or ￥1,200.00
    r"|(\d[\d,]*(?:\.\d{1,2})?)\s*元"             # 1200元
    r"|(?:售价|出|价格|标价|到手价|包邮)\s*(\d[\d,]*(?:\.\d{1,2})?))"  # 售价1200
)


def _extract_ids(text: str) -> list[str]:
    ids = []
    seen = set()
    for m in GOOFISH_ID_RE.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def _extract_price(text: str) -> float | None:
    for m in PRICE_RE.finditer(text):
        raw = m.group(1) or m.group(2) or m.group(3)
        if raw:
            try:
                return float(raw.replace(",", ""))
            except ValueError:
                continue
    return None


async def _scrape_bing_page(context, query: str, first: int = 0) -> list[dict]:
    """Scrape one page of Bing results for goofish item links."""
    encoded = quote_plus(f"site:goofish.com/item {query}")
    url = f"https://www.bing.com/search?q={encoded}&count=10&first={first}"

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)
        return await page.evaluate("""() => {
            const items = [];
            document.querySelectorAll('.b_algo').forEach(algo => {
                const a = algo.querySelector('h2 a');
                const cite = algo.querySelector('cite');
                const snippet = algo.querySelector('.b_caption p');
                if (cite && cite.textContent.includes('item')) {
                    items.push({
                        title: a?.textContent?.trim() || '',
                        href: a?.href || '',
                        snippet: snippet?.textContent?.trim() || '',
                    });
                }
            });
            return items;
        }""")
    except Exception as exc:
        log.warning("Bing search failed (first=%d): %s", first, exc)
        return []
    finally:
        await page.close()


async def _follow_redirect(context, href: str) -> str | None:
    """Follow a Bing redirect link and return the goofish item ID."""
    new_page = await context.new_page()
    try:
        await new_page.goto(href, wait_until="domcontentloaded", timeout=10000)
        await new_page.wait_for_timeout(2000)
        m = GOOFISH_ID_RE.search(new_page.url)
        return m.group(1) if m else None
    except Exception:
        try:
            m = GOOFISH_ID_RE.search(new_page.url)
            return m.group(1) if m else None
        except Exception:
            return None
    finally:
        await new_page.close()


def _clean_result(item_id: str, sr: dict) -> dict | None:
    """Build an item dict from a search result, or None if it should be skipped."""
    title = sr["title"].replace("_闲鱼", "").replace(" - 闲鱼", "").strip()
    if not title or ("闲鱼" in title and len(title) < 20):
        return None

    snippet = sr["snippet"]
    if snippet.startswith("闲鱼，中国领先的闲置二手交易平台"):
        snippet = ""

    return {
        "id": item_id,
        "title": title,
        "price": _extract_price(title + " " + snippet),
        "images": [],
        "seller": "",
        "location": "",
        "status": "on_sale",
        "url": f"https://www.goofish.com/item?id={item_id}",
        "description": snippet,
        "source": "bing_search",
    }


_redirect_sem = asyncio.Semaphore(3)


async def _follow_redirect_bounded(context, href: str) -> str | None:
    async with _redirect_sem:
        return await _follow_redirect(context, href)


async def discover_items_with_browser(context, query: str, original_query: str = "", max_items: int = 20) -> list[dict]:
    """Find Goofish items by searching Bing pages 1+2, following redirects in parallel."""
    items = []
    seen = set()

    queries = [query]
    if original_query and original_query != query:
        queries.append(original_query)

    for q in queries:
        if len(items) >= max_items:
            break

        all_results = []
        for first in (0, 10):
            if len(items) + len(all_results) >= max_items + 5:
                break
            page_results = await _scrape_bing_page(context, q, first)
            all_results.extend(page_results)

        log.info("Bing returned %d item results for %r", len(all_results), q)

        # Resolve redirects in parallel (bounded by semaphore)
        candidates = [sr for sr in all_results if sr.get("href")][:max_items - len(items) + 5]
        resolved = await asyncio.gather(
            *[_follow_redirect_bounded(context, sr["href"]) for sr in candidates],
            return_exceptions=True,
        )

        for sr, item_id in zip(candidates, resolved):
            if len(items) >= max_items:
                break
            if isinstance(item_id, Exception) or not item_id or item_id in seen:
                continue
            seen.add(item_id)
            log.info("Discovered item %s: %s", item_id, sr.get("title", "")[:40])

            item = _clean_result(item_id, sr)
            if item:
                items.append(item)

    return items[:max_items]


# Keep old function name for backward compat
async def discover_item_ids_with_browser(context, query: str, original_query: str = "", max_items: int = 20) -> list[str]:
    items = await discover_items_with_browser(context, query, original_query, max_items)
    return [i["id"] for i in items]


def extract_item_id_from_url(url: str) -> str | None:
    m = GOOFISH_ID_RE.search(url)
    return m.group(1) if m else None
