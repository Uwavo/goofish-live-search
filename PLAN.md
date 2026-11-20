# Goofish Live Search — Architecture & Implementation Plan

## 1. Directory Structure

```
goofish-live-search/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, lifespan (browser init/shutdown)
│   ├── routes.py             # /api/search, /api/item/{id}, /api/health
│   ├── browser_engine.py     # Playwright live-fetch engine
│   ├── cache.py              # SQLite cache with TTL
│   ├── rate_limiter.py       # Adaptive per-IP rate limiter
│   ├── normalizer.py         # JSON/HTML parsing, image URL cleanup, status mapping
│   └── config.py             # Settings (timeouts, cache TTL, rate limits)
├── frontend/
│   ├── index.html            # Single-page UI (vanilla HTML + Tailwind CSS + JS)
│   └── app.js                # Search, filters, pagination, results rendering
├── tests/
│   ├── __init__.py
│   ├── test_normalizer.py    # Unit: JSON parsing, URL normalization, price filtering
│   ├── test_cache.py         # Unit: SQLite TTL, insert/retrieve/expire
│   ├── test_live.py          # Integration: real Goofish search + item detail
│   └── test_e2e.py           # E2E: Playwright against localhost UI
├── requirements.txt
├── .gitignore
├── README.md
└── PLAN.md
```

## 2. Browser Engine Design (No-Login Live Fetch)

### Technology
- **Playwright** with bundled open-source **Chromium**
- Single persistent browser context reused across requests (reduces startup cost)
- Stealth flags: `--disable-blink-features=AutomationControlled`, realistic viewport (1366×768), `en-US,en` locale, standard user-agent rotation from a small built-in list

### Search Flow (`/api/search`)
1. Navigate to `https://www.goofish.com/search?q={query}&sort={sort}` with optional price params
2. **Network response interception**: listen for XHR/fetch responses matching Goofish's search API pattern (e.g., URLs containing `/search` or `/mtop` JSON endpoints)
3. When the JSON response is captured, extract listing data directly from the JSON payload — this is the fastest and most reliable path
4. **Fallback**: if network interception yields nothing within timeout, parse `window.__INIT_DATA__` or `__NEXT_DATA__` from the page HTML via `page.evaluate()`
5. Dismiss any login/QR overlay popups by detecting and clicking close buttons (`.close-btn`, `[class*="close"]`, overlay backdrop click)

### Item Detail Flow (`/api/item/{id}`)
1. Navigate to `https://www.goofish.com/item/{id}`
2. Same interception strategy: capture item detail JSON from network, fallback to `__INIT_DATA__`
3. Extract: title, price, all image URLs, seller nickname, location, item status, description

### Image URL Normalization
- Goofish/Alibaba CDN appends size suffixes like `_200x200.jpg`, `_100x100q90.jpg`
- Strip these suffixes to get original resolution: regex replace `_\d+x\d+[a-z]*\d*\.` → `.`
- Validate URLs return HTTP 200 with `Content-Type: image/*`

### Popup Dismissal
- After each navigation, run a quick DOM check (100ms delay) for common overlay selectors
- Click-dismiss or remove the overlay node
- No login interaction — purely closing the popup

### Pagination
- Goofish search paginates via scroll-to-load
- Simulate scroll via `page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))`
- Wait for new network responses, capture additional results
- API accepts `page` param; engine scrolls N times to reach page N

## 3. Backend & Caching Layer

### FastAPI Endpoints

| Endpoint | Method | Params | Returns |
|---|---|---|---|
| `/api/health` | GET | — | `{"status": "ok", "browser": true/false}` |
| `/api/search` | GET | `q`, `min_price`, `max_price`, `sort` (default/price_asc/price_desc), `page` (1-based) | `{"items": [...], "total": int, "page": int}` |
| `/api/item/{id}` | GET | — | `{"id", "title", "price", "images", "seller", "location", "status", "url", "description"}` |

### SQLite Cache (`cache.db`)
- Table: `cache(key TEXT PRIMARY KEY, data TEXT, created_at REAL)`
- Key = hash of endpoint + params
- TTL: **10 minutes** (configurable)
- On read: check `created_at`; if expired, delete and re-fetch
- Periodic cleanup of expired rows on write (every 50 writes)

### Adaptive Rate Limiter
- Token bucket per unique search query pattern
- Default: max 6 requests/minute to Goofish
- If a request gets a CAPTCHA or 403, back off exponentially (double the interval, cap at 60s)
- Cache hits bypass the rate limiter entirely

### Static File Serving
- FastAPI mounts `/` to serve `frontend/` directory
- `index.html` served at root

## 4. Frontend UI

### Tech Stack
- **HTML5** + **Tailwind CSS** (CDN) + **vanilla JavaScript**
- No build step, no npm — just open the page

### Features
- **Search bar** with real-time submit (Enter or button)
- **Filters**: min price, max price, sort dropdown (relevance / price low→high / price high→low)
- **Results grid**: responsive card layout showing thumbnail, title, price (¥), location, status badge
- **Image modal**: click thumbnail to see full-res image gallery
- **Direct link**: each card has a "View on Goofish" button opening the real listing
- **Pagination**: "Load More" button fetching next page
- **Loading states**: skeleton cards while fetching
- **Error handling**: toast notifications for network errors, rate limits, empty results

### Design
- Clean white/gray theme, Chinese yuan formatting
- Mobile-responsive (cards stack on small screens)
- Status badges: green "On Sale" / red "Sold"

## 5. Testing Strategy

### Unit Tests (`pytest`)
- `test_normalizer.py`: image URL stripping, JSON → listing dict mapping, price filter logic, status detection
- `test_cache.py`: insert, retrieve before TTL, retrieve after TTL (expired), cleanup

### Live Integration Tests (`pytest` + Playwright)
- `test_live.py`: run a real search for a common keyword (e.g., "手机壳"), assert ≥1 result returned with valid fields; fetch one item detail and assert images are valid URLs
- Marked with `@pytest.mark.live` so they can be skipped in CI

### End-to-End Tests (`pytest` + Playwright)
- `test_e2e.py`: start FastAPI server, open `localhost:8000` in Playwright browser, type a search, assert result cards appear, click "View on Goofish" and assert new tab URL matches `goofish.com/item/`

## 6. Deployment / GitHub Publishing

- `.gitignore`: `__pycache__/`, `*.pyc`, `cache.db`, `.env`, `venv/`, `node_modules/`
- `README.md`: project description, prerequisites (Python 3.10+), setup steps (`pip install`, `playwright install chromium`), run command, test command, screenshots
- `gh repo create goofish-live-search --public --source=. --push`

---

**Awaiting your approval to proceed to Phase 2 (implementation).**
