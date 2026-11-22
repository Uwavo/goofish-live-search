from fastapi import APIRouter, HTTPException, Query

from backend.browser_engine import get_context, is_browser_ready
from backend.cache import cache_key, get_cached, set_cached
from backend.discovery import discover_items_with_browser
from backend.normalizer import filter_by_price
from backend.translator import translate_query

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "browser": await is_browser_ready()}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    include_sold: bool = Query(False),
    page: int = Query(1, ge=1),
):
    key = cache_key("search_v2", {"q": q, "page": page, "include_sold": include_sold})
    cached = get_cached(key)
    if cached is not None:
        items = filter_by_price(cached, min_price, max_price)
        return {"items": items, "total": len(items), "page": page, "query_translated": q}

    translated = translate_query(q)

    try:
        ctx = get_context()
        if not ctx:
            raise HTTPException(status_code=503, detail="Browser not ready")
        items = await discover_items_with_browser(ctx, translated, original_query=q, max_items=20)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Discovery failed: {exc}")

    if not include_sold:
        items = [i for i in items if i.get("status") != "sold"]

    set_cached(key, items)
    items = filter_by_price(items, min_price, max_price)
    return {
        "items": items,
        "total": len(items),
        "page": page,
        "query_translated": translated,
        "discovered": len(items),
    }
