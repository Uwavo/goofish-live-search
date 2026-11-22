"""Discover Goofish items via Bing search and extract metadata."""
import logging
import re
from urllib.parse import quote_plus

log = logging.getLogger(__name__)

GOOFISH_ID_RE = re.compile(r"goofish\.com/item[/?](?:id=)?(\d{10,})")
PRICE_RE = re.compile(r"[¥￥]?\s*(\d+(?:\.\d{1,2})?)\s*(?:元|¥|￥)")


def _extract_ids(text: str) -> list[str]:
    ids = []
    seen = set()
    for m in GOOFISH_ID_RE.finditer(text):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def _extract_price(text: str) -> float | None:
    m = PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    nums = re.findall(r"(\d{2,6}(?:\.\d{1,2})?)", text)
    return None


async def discover_items_with_browser(context, query: str, original_query: str = "", max_items: int = 20) -> list[dict]:
    """Find Goofish items by searching Bing, following redirects, and extracting metadata from search results."""
    items = []
    seen = set()

    queries = [query]
    if original_query and original_query != query:
        queries.append(original_query)

    for q in queries:
        if len(items) >= max_items:
            break

        encoded = quote_plus(f"site:goofish.com/item {q}")
        url = f"https://www.bing.com/search?q={encoded}&count=30"

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            search_results = await page.evaluate("""() => {
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
            log.warning("Bing search failed: %s", exc)
            search_results = []
        finally:
            await page.close()

        log.info("Bing returned %d item results for %r", len(search_results), q)

        for sr in search_results:
            if len(items) >= max_items:
                break
            if not sr.get("href"):
                continue

            # Follow Bing redirect to get real item URL + ID
            new_page = await context.new_page()
            item_id = None
            try:
                await new_page.goto(sr["href"], wait_until="domcontentloaded", timeout=10000)
                await new_page.wait_for_timeout(2000)
                final_url = new_page.url
                m = GOOFISH_ID_RE.search(final_url)
                if m:
                    item_id = m.group(1)
            except Exception:
                try:
                    final_url = new_page.url
                    m = GOOFISH_ID_RE.search(final_url)
                    if m:
                        item_id = m.group(1)
                except Exception:
                    pass
            finally:
                await new_page.close()

            if not item_id or item_id in seen:
                log.debug("Redirect %s -> no item ID or dupe", sr.get("title", "")[:30])
                continue
            seen.add(item_id)
            log.info("Discovered item %s: %s", item_id, sr.get("title", "")[:40])

            title = sr["title"].replace("_闲鱼", "").replace(" - 闲鱼", "").strip()
            if not title or "闲鱼" in title and len(title) < 20:
                continue

            snippet = sr["snippet"]
            if snippet.startswith("闲鱼，中国领先的闲置二手交易平台"):
                snippet = ""

            price = _extract_price(snippet)

            items.append({
                "id": item_id,
                "title": title,
                "price": price,
                "images": [],
                "seller": "",
                "location": "",
                "status": "on_sale",
                "url": f"https://www.goofish.com/item?id={item_id}",
                "description": snippet,
                "source": "bing_search",
            })

    return items[:max_items]


# Keep old function name for backward compat
async def discover_item_ids_with_browser(context, query: str, original_query: str = "", max_items: int = 20) -> list[str]:
    items = await discover_items_with_browser(context, query, original_query, max_items)
    return [i["id"] for i in items]


def extract_item_id_from_url(url: str) -> str | None:
    m = GOOFISH_ID_RE.search(url)
    return m.group(1) if m else None
