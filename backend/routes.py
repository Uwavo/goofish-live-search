from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.browser_engine import (
    clear_session,
    get_context,
    get_session_status,
    is_browser_ready,
    open_login_window,
    search_authenticated,
)
from backend.cache import cache_key, get_cached, set_cached
from backend.config import CNY_TO_GBP_RATE, SPAM_KEYWORDS
from backend.currency import cny_to_gbp
from backend.deals import compute_deal_score, get_saved_deals, get_saved_ids, remove_deal, save_deal
from backend.discovery import discover_items_with_browser
from backend.normalizer import filter_by_price
from backend.translator import translate_query

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "browser": await is_browser_ready(),
        "session": get_session_status(),
    }


@router.get("/session/status")
async def session_status():
    return {"status": get_session_status()}


@router.post("/session/login")
async def session_login():
    result = await open_login_window()
    return result


@router.post("/session/logout")
async def session_logout():
    await clear_session()
    return {"status": "guest"}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    include_sold: bool = Query(False),
    sort: str = Query("relevance"),
    category: str = Query("all"),
    filter_spam: bool = Query(True),
    page: int = Query(1, ge=1),
):
    key = cache_key("search_v3", {"q": q, "page": page, "include_sold": include_sold, "cat": category})
    cached = get_cached(key)
    if cached is not None:
        items = _post_process(cached, min_price, max_price, sort, filter_spam)
        return _build_response(items, q, q, page)

    translated = translate_query(q)

    if category != "all":
        from backend.config import CATEGORIES
        cat_term = CATEGORIES.get(category, "")
        if cat_term:
            translated = f"{translated} {cat_term}"

    items = None
    source = "bing_search"

    # Try authenticated search first
    if get_session_status() == "connected":
        items = await search_authenticated(translated)
        if items:
            source = "goofish_live"

    # Fallback to Bing discovery
    if not items:
        try:
            ctx = get_context()
            if not ctx:
                raise HTTPException(status_code=503, detail="Browser not ready")
            items = await discover_items_with_browser(ctx, translated, original_query=q, max_items=20)
            source = "bing_search"
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Discovery failed: {exc}")

    if not items:
        items = []

    if not include_sold:
        items = [i for i in items if i.get("status") != "sold"]

    # Add GBP prices and deal scores
    all_prices = [i["price"] for i in items if i.get("price")]
    saved = get_saved_ids()
    for item in items:
        item["price_gbp"] = cny_to_gbp(item.get("price"))
        item["deal_score"] = compute_deal_score(item.get("price"), all_prices)
        item["saved"] = item.get("id", "") in saved
        item.setdefault("source", source)

    set_cached(key, items)
    items = _post_process(items, min_price, max_price, sort, filter_spam)
    return _build_response(items, q, translated, page)


def _post_process(items, min_price, max_price, sort, filter_spam):
    items = filter_by_price(items, min_price, max_price)
    if filter_spam:
        items = [i for i in items if not any(kw in (i.get("title", "") + i.get("description", "")) for kw in SPAM_KEYWORDS)]
    if sort == "price_asc":
        items.sort(key=lambda x: x.get("price") or float("inf"))
    elif sort == "price_desc":
        items.sort(key=lambda x: x.get("price") or 0, reverse=True)
    elif sort == "deal":
        items.sort(key=lambda x: x.get("deal_score") or 0, reverse=True)
    return items


def _build_response(items, q, translated, page):
    return {
        "items": items,
        "total": len(items),
        "page": page,
        "query_translated": translated if translated != q else None,
        "discovered": len(items),
        "session": get_session_status(),
        "rate": CNY_TO_GBP_RATE,
    }


class SaveDealRequest(BaseModel):
    item: dict


@router.post("/deals/save")
async def api_save_deal(req: SaveDealRequest):
    save_deal(req.item)
    return {"ok": True}


@router.delete("/deals/{item_id}")
async def api_remove_deal(item_id: str):
    remove_deal(item_id)
    return {"ok": True}


@router.get("/deals")
async def api_get_deals():
    deals = get_saved_deals()
    for d in deals:
        d["price_gbp"] = cny_to_gbp(d.get("price"))
        d["saved"] = True
    return {"items": deals, "total": len(deals)}
