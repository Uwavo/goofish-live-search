from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field
from typing import Optional

from backend.browser_engine import (
    clear_session,
    get_context,
    get_session_status,
    is_browser_ready,
    is_verified_connected,
    open_login_window,
    search_authenticated,
)
from backend.cache import cache_key, get_cached, set_cached
from backend.config import CNY_TO_GBP_RATE, SPAM_KEYWORDS
from backend.currency import cny_to_gbp
from backend.deals import compute_deal_score, get_saved_deals, get_saved_ids, remove_deal, save_deal
from backend.discovery import discover_items_with_browser
from backend.normalizer import filter_by_price
from backend.rapidapi_client import (
    batch_lookup as rapidapi_batch_lookup,
    get_item_detail as rapidapi_get_detail,
    get_status as rapidapi_get_status,
    is_configured as rapidapi_is_configured,
    search_listings as rapidapi_search,
    set_api_key as rapidapi_set_key,
    set_page_size as rapidapi_set_page_size,
)
from backend.translator import translate_query

router = APIRouter(prefix="/api")


def _require_xhr(x_requested_with: Optional[str]) -> None:
    if x_requested_with != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="Missing or invalid X-Requested-With header")


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
async def session_login(x_requested_with: Optional[str] = Header(None)):
    _require_xhr(x_requested_with)
    result = await open_login_window()
    return result


@router.post("/session/logout")
async def session_logout(x_requested_with: Optional[str] = Header(None)):
    _require_xhr(x_requested_with)
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
    personal_only: bool = Query(False),
    free_shipping: bool = Query(False),
    brand_new: bool = Query(False),
    inspected_only: bool = Query(False),
    publish_days: int | None = Query(None),
):
    key = cache_key("search_v5", {
        "q": q, "page": page, "include_sold": include_sold, "cat": category,
        "min": min_price, "max": max_price, "sort": sort, "spam": filter_spam,
        "personal": personal_only, "freeship": free_shipping,
        "new": brand_new, "inspected": inspected_only, "pubdays": publish_days,
    })
    cached = get_cached(key)
    if cached is not None:
        return _build_response(cached, q, q, page)

    translated = translate_query(q)

    if category != "all":
        from backend.config import CATEGORIES
        cat_term = CATEGORIES.get(category, "")
        if cat_term:
            translated = f"{translated} {cat_term}"

    items = None
    source = "bing_search"

    # Priority 1: Authenticated mtop search (free, best quality)
    if is_verified_connected():
        items = await search_authenticated(translated)
        if items:
            source = "goofish_live"

    # Priority 2: RapidAPI search (real images, exact prices, native filters)
    if not items and rapidapi_is_configured():
        items = await rapidapi_search(
            translated,
            page=page,
            min_price=min_price,
            max_price=max_price,
            sort=sort,
            personal_only=personal_only,
            free_shipping=free_shipping,
            brand_new=brand_new,
            inspected_only=inspected_only,
            publish_days=publish_days,
        )
        if items:
            source = "rapidapi"

    # Priority 3: Bing discovery (free, no images)
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

    all_prices = [i["price"] for i in items if i.get("price")]
    saved = get_saved_ids()
    for item in items:
        item["price_gbp"] = cny_to_gbp(item.get("price"))
        item["deal_score"] = compute_deal_score(item.get("price"), all_prices)
        item["saved"] = item.get("id", "") in saved
        item.setdefault("source", source)

    items = _post_process(items, min_price, max_price, sort, filter_spam)
    set_cached(key, items)
    return _build_response(items, q, translated, page)


def _post_process(items, min_price, max_price, sort, filter_spam):
    items = filter_by_price(items, min_price, max_price)
    if filter_spam:
        items = [i for i in items if not any(kw in ((i.get("title") or "") + (i.get("description") or "")).lower() for kw in SPAM_KEYWORDS)]
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
        "rapidapi": rapidapi_get_status(),
    }


@router.get("/search/live")
async def search_live(
    q: str = Query(..., min_length=1),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort: str = Query("relevance"),
    category: str = Query("all"),
    filter_spam: bool = Query(True),
):
    if not is_verified_connected():
        raise HTTPException(
            status_code=401,
            detail="You need to sign in via Alipay first to unlock Full Access.",
        )

    translated = translate_query(q)
    if category != "all":
        from backend.config import CATEGORIES
        cat_term = CATEGORIES.get(category, "")
        if cat_term:
            translated = f"{translated} {cat_term}"

    items = await search_authenticated(translated)
    if not items:
        items = []

    all_prices = [i["price"] for i in items if i.get("price")]
    saved = get_saved_ids()
    for item in items:
        item["price_gbp"] = cny_to_gbp(item.get("price"))
        item["deal_score"] = compute_deal_score(item.get("price"), all_prices)
        item["saved"] = item.get("id", "") in saved
        item["source"] = "goofish_live"

    items = _post_process(items, min_price, max_price, sort, filter_spam)
    return _build_response(items, q, translated, 1)


class DealItem(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    title: str = Field("", max_length=500)
    price: Optional[float] = None
    url: str = Field("", max_length=1000)
    description: str = Field("", max_length=2000)
    images: list[str] = Field(default_factory=list)
    seller: str = Field("", max_length=200)
    location: str = Field("", max_length=200)
    source: str = Field("", max_length=50)
    deal_score: Optional[int] = None
    price_gbp: Optional[float] = None
    status: str = Field("on_sale", max_length=20)


class SaveDealRequest(BaseModel):
    item: DealItem


@router.post("/deals/save")
async def api_save_deal(req: SaveDealRequest, x_requested_with: Optional[str] = Header(None)):
    _require_xhr(x_requested_with)
    save_deal(req.item.model_dump())
    return {"ok": True}


@router.delete("/deals/{item_id}")
async def api_remove_deal(item_id: str, x_requested_with: Optional[str] = Header(None)):
    _require_xhr(x_requested_with)
    remove_deal(item_id)
    return {"ok": True}


@router.get("/deals")
async def api_get_deals():
    deals = get_saved_deals()
    for d in deals:
        d["price_gbp"] = cny_to_gbp(d.get("price"))
        d["saved"] = True
    return {"items": deals, "total": len(deals)}


# ── RapidAPI Settings ──

@router.get("/rapidapi/status")
async def rapidapi_status():
    return rapidapi_get_status()


class RapidApiKeyRequest(BaseModel):
    key: str = Field("", max_length=200)
    page_size: int | None = Field(None, ge=1, le=30)


@router.post("/rapidapi/settings")
async def rapidapi_settings(req: RapidApiKeyRequest, x_requested_with: Optional[str] = Header(None)):
    _require_xhr(x_requested_with)
    if req.key is not None:
        rapidapi_set_key(req.key)
    if req.page_size is not None:
        rapidapi_set_page_size(req.page_size)
    return rapidapi_get_status()


@router.get("/item/{item_id}/detail")
async def item_detail(item_id: str):
    detail = await rapidapi_get_detail(item_id)
    if detail:
        return detail
    raise HTTPException(status_code=404, detail="Item detail not available")
