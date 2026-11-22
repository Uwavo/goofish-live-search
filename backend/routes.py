from fastapi import APIRouter, HTTPException, Query

from backend.browser_engine import get_item_detail, is_browser_ready, search_goofish
from backend.cache import cache_key, get_cached, set_cached
from backend.normalizer import filter_by_price

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "browser": await is_browser_ready()}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort: str = Query("default", pattern="^(default|price_asc|price_desc)$"),
    page: int = Query(1, ge=1),
):
    key = cache_key("search", {"q": q, "sort": sort, "page": page})
    cached = get_cached(key)
    if cached is not None:
        result = cached
    else:
        try:
            result = await search_goofish(q, sort=sort, page_num=page)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        set_cached(key, result)

    items = filter_by_price(result["items"], min_price, max_price)
    return {"items": items, "total": len(items), "page": page, "source": result.get("source", "unknown")}


@router.get("/item/{item_id}")
async def item_detail(item_id: str):
    key = cache_key("item", {"id": item_id})
    cached = get_cached(key)
    if cached is not None:
        return cached

    try:
        detail = await get_item_detail(item_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if detail is None:
        raise HTTPException(status_code=404, detail="Item not found")

    set_cached(key, detail)
    return detail
