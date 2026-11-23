<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/tests-114%20passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
</p>

# Goofish Live Search

A local dashboard for searching [Goofish (闲鱼)](https://www.goofish.com) — China's largest second-hand marketplace. Runs on `localhost:1212` with three modes: **Guest** (Bing-only, no account), **RapidAPI Guest** (HD images + exact prices, no Goofish account), and **Full Access** (Alipay QR login).

Built for UK resellers who want to source from Goofish without navigating Chinese UI.

---

## Features

| | Guest (Free) | Guest + RapidAPI | Full Access |
|---|---|---|---|
| **Search** | Bing web index | RapidAPI Goofish API | Local mtop API |
| **Results** | ~10 per query | 30 per page + Load More | 20+ per query |
| **Images** | No | HD galleries | Full galleries |
| **Prices** | Snippet extraction | Exact CNY | Exact CNY |
| **Seller info** | No | Nickname + location | Full |
| **Native filters** | No | Personal / Free Ship / New / Price Drop | Category only |
| **Account needed** | None | RapidAPI key only | Alipay QR scan |
| **Cost** | Free | Per RapidAPI plan | Free |

**All modes include:**
- Auto English → Chinese translation (MyMemory API, cached in-memory)
- Deal scoring (0–100 based on price vs median)
- CNY → GBP conversion toggle
- Save/unsave deals (persisted in SQLite)
- Spam filtering (hides junk like 维修, 主板坏, 配件机)
- Anti-ban protections (1.5–3.5s jitter, 15-min cache, cooldown on 403)
- Category tabs (phones, electronics, computers, fashion, sneakers, cameras, gaming, home)

---

## Quick Start

```bash
git clone https://github.com/Uwavo/goofish-live-search.git
cd goofish-live-search
pip install -r requirements.txt
playwright install chromium
python -m uvicorn backend.main:app --host 0.0.0.0 --port 1212 --loop asyncio
```

Open **http://localhost:1212**

---

## How It Works

### Guest Mode (Free, no account)
```
English query → MyMemory translation → Bing "site:goofish.com/item <query>"
  → scrape 2 pages → follow redirects (3 concurrent) → extract IDs + prices
```

### Guest + RapidAPI (no Goofish account needed)
```
English or Chinese query → GET /search_goofish_listings (keyword, filters, sort)
  → HD images, exact CNY prices, seller info, sold status
  → native marketplace filters: personal sellers, free shipping, brand new, price drops
```
Set your RapidAPI key in **Settings → RapidAPI Key** or in `.env` as `RAPIDAPI_KEY`. The API accepts English keywords directly (no translation step needed, though we still translate for consistency).

### Full Access (Alipay QR)
```
"Link Alipay Account" → visible browser opens → scan QR with Alipay app
  → cookies saved to ./data/session_state.json
  → verified against Goofish mtop API (real search probe)
  → all future searches use mtop for real-time results
```

Session persists across restarts. On startup, the backend re-verifies the saved session via mtop — cookie files alone are never trusted.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (localhost:1212)                                     │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Free Search  │  │   Live   │  │  Saved   │  │ Account  │ │
│  │  (Bing)     │  │ (mtop)   │  │  Deals   │  │ (Alipay) │ │
│  └──────┬──────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
└─────────┼──────────────┼─────────────┼──────────────┼────────┘
          │              │             │              │
          ▼              ▼             ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend (:1212)                                      │
│                                                               │
│  GET /api/search ──┐                                          │
│                    ├─→ Verified?  → mtop API (Playwright)     │
│                    ├─→ RapidAPI?  → Goofish API (httpx)       │
│                    └─→ Guest?    → Bing scrape (Playwright)   │
│                                                               │
│  POST /api/session/login ──→ Visible Chromium + Alipay QR     │
│  POST /api/deals/save ────→ SQLite (WAL mode)                 │
│                                                               │
│  CSRF: X-Requested-With header required on all mutations      │
│  CORS: locked to localhost origins only                        │
└──────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────┐
│  ./data/                                                      │
│  ├── session_state.json   (Alipay session cookies)            │
│  ├── saved_deals.db       (SQLite — saved deals)              │
│  ├── cache.db             (SQLite — search cache, 15min TTL)  │
│  ├── browser_profile/     (Chromium persistent context)       │
│  └── login_profile/       (Chromium login window context)     │
└──────────────────────────────────────────────────────────────┘
```

---

## API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/health` | GET | — | Health check + browser/session status |
| `/api/session/status` | GET | — | Returns `guest` or `connected` |
| `/api/session/login` | POST | CSRF | Opens Alipay QR login window |
| `/api/session/logout` | POST | CSRF | Clears session + cookies |
| `/api/search` | GET | — | Dual-mode search (auto-selects guest/live) |
| `/api/search/live` | GET | Verified | Live search only (401 if not connected) |
| `/api/deals/save` | POST | CSRF | Save a deal (validated with Pydantic) |
| `/api/deals/{item_id}` | DELETE | CSRF | Remove a saved deal |
| `/api/deals` | GET | — | List all saved deals |

**Search parameters:** `q` (required), `min_price`, `max_price`, `sort` (relevance/price_asc/price_desc/deal), `category`, `filter_spam`, `include_sold`, `page`

**CSRF:** State-changing endpoints require `X-Requested-With: XMLHttpRequest` header.

---

## Security

- **No XSS** — all DOM rendering uses `createElement` + `textContent`, zero `innerHTML` with user data
- **CSRF protection** — custom header check on all POST/DELETE endpoints
- **CORS locked** — only `localhost:1212` / `127.0.0.1:1212` / `0.0.0.0:1212`
- **Input validation** — Pydantic models with field length limits on all write endpoints
- **No credentials stored** — Alipay login happens in a sandboxed browser; no passwords touch the backend
- **Session verification** — mtop API probe on every startup; cookie files alone never grant access
- **Concurrency safe** — `asyncio.Lock` on session state, SQLite WAL mode with 10s timeout

---

## Tests

```bash
# Run all unit tests (114 tests)
python -m pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_e2e.py -q

# E2E tests (requires running server)
python -m pytest tests/test_e2e.py -v
```

**Coverage:** cookie validation, placeholder rejection, session gating, route locking, deal scoring, price parsing, URL normalisation, cache TTL, SQLite roundtrips, WAL mode init, price filter edge cases.

---

## Project Structure

```
backend/
├── main.py             FastAPI app, lifespan (DB init + browser)
├── routes.py           All API endpoints + Pydantic models
├── browser_engine.py   Playwright engine, session mgmt, mtop verification
├── discovery.py        Bing scraping + parallel redirect resolution
├── translator.py       English→Chinese (MyMemory, LRU cached)
├── normalizer.py       Price parsing, image URLs, listing normalisation
├── currency.py         CNY↔GBP conversion
├── deals.py            Deal scoring + SQLite persistence
├── rapidapi_client.py  RapidAPI Goofish search, detail, batch + settings
├── cache.py            SQLite TTL cache (15 min)
└── config.py           All settings (port, jitter, categories, spam words)

frontend/
├── index.html          Dashboard UI (Tailwind CSS)
└── app.js              Search, cards, drawer, session, saved deals

tests/
├── test_session.py     Cookie validation + session state (17 tests)
├── test_routes_lock.py Full Access gating (2 tests)
├── test_deals.py       Deal scoring + SQLite + DB init (12 tests)
├── test_normalizer.py  Price/URL/filter tests (16 tests)
├── test_discovery.py   Bing scraping + price extraction
├── test_currency.py    CNY/GBP conversion
├── test_translator.py  Translation detection
├── test_rapidapi.py    RapidAPI client, normalize, fallback, settings (32 tests)
├── test_cache.py       Cache TTL + DB init
└── test_e2e.py         Playwright E2E (requires server)

data/                   (gitignored) runtime state
```

---

## Configuration

All settings via environment variables or `backend/config.py`:

| Variable | Default | Description |
|---|---|---|
| `RAPIDAPI_KEY` | _(none)_ | RapidAPI key for Guest Mode enrichment (or set in Settings UI) |
| `PORT` | `1212` | Server port |
| `CNY_GBP_RATE` | `0.11` | Exchange rate for price display |
| `CACHE_TTL` | `900` | Search cache TTL in seconds |
| `RATE_LIMIT` | `6` | Max searches per minute |
| `BROWSER_TIMEOUT` | `30000` | Playwright timeout (ms) |
| `NAV_TIMEOUT` | `20000` | Page navigation timeout (ms) |

---

## Limitations

- **No images in free guest mode** — Goofish blocks item content without login (use RapidAPI to get images without an account)
- **~10 results in free guest mode** — limited by Bing's index coverage
- **Free guest prices are best-effort** — extracted from Bing snippet text
- **Alipay app required for Full Access** — no username/password login supported
- **Single user** — designed for local use, not multi-tenant

---

## Tech Stack

**Backend:** Python 3.10+, FastAPI, Playwright, SQLite (WAL), Pydantic v2

**Frontend:** HTML5, Tailwind CSS, vanilla JavaScript (no framework)

**Testing:** pytest, 114 unit tests
