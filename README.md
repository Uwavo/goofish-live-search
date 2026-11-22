# Goofish Live Search

100% account-free search engine for [Goofish (闲鱼)](https://www.goofish.com) — China's largest second-hand marketplace.

Discovers real listings via public Bing search indexes, auto-translates English queries to Chinese, and displays results in a clean dashboard. **No Goofish account required.**

## How It Works

1. **Search** — Type an English or Chinese query (e.g. "sony camera", "手机壳")
2. **Translate** — English queries are automatically translated to Chinese via MyMemory API
3. **Discover** — Bing is searched for `site:goofish.com/item <query>` across multiple pages, redirect links are followed to extract real item IDs
4. **Display** — Item titles, descriptions, and prices (when available) are extracted from Bing search result snippets

## Architecture

```
Frontend (Tailwind CSS) → FastAPI Backend → Playwright Browser
                                              ↓
                                         Bing Search (pages 1 & 2)
                                              ↓
                                      Redirect Following
                                              ↓
                                    Item ID + Metadata Extraction
```

- **Backend:** FastAPI + Uvicorn on port `1212`
- **Browser:** Playwright Chromium with persistent profile (anti-detection)
- **Translation:** MyMemory API (free, no key required)
- **Discovery:** Bing web search with multi-page scraping and deduplication
- **Price extraction:** Regex parser for Chinese currency formats (¥1200, 1200元, 售价1200, etc.)
- **Cache:** In-memory TTL cache for repeat queries

## Prerequisites

- Python 3.10+
- Windows/macOS/Linux

## Setup

```bash
git clone https://github.com/Uwavo/goofish-live-search.git
cd goofish-live-search
pip install -r requirements.txt
playwright install chromium
```

## Run

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 1212 --loop asyncio
```

Open [http://localhost:1212](http://localhost:1212)

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Health check + browser status |
| `GET /api/search?q=keyword&min_price=10&max_price=100` | Search listings |

## Tests

```bash
# Unit tests
python -m pytest tests/ --ignore=tests/test_live.py -q

# Live end-to-end test (requires internet + Chromium)
python tests/verify_live.py
```

## Limitations

- **No product images** — Goofish blocks item page content without login; images are not indexed by search engines
- **~10 results per query** — limited by what Bing has indexed for goofish.com
- **Price extraction is best-effort** — prices only appear when mentioned in the Bing search snippet text

## Project Structure

```
backend/
  main.py          — FastAPI app + lifespan
  routes.py        — /api/search, /api/health
  discovery.py     — Bing multi-page search + redirect following
  translator.py    — English→Chinese via MyMemory API
  browser_engine.py— Playwright persistent context
  normalizer.py    — Price parsing, image URL cleaning
  cache.py         — In-memory TTL cache
  rate_limiter.py  — Request throttling
  config.py        — Port 1212, timeouts, user agents
frontend/
  index.html       — Dashboard UI (Tailwind CSS)
  app.js           — Search + card rendering
tests/
  test_*.py        — Unit tests
  verify_live.py   — Live E2E verification
```

## Tech Stack

- **Backend:** Python, FastAPI, Playwright
- **Frontend:** HTML, Tailwind CSS, vanilla JavaScript
- **Testing:** pytest
