# Goofish Live Search

Dual-mode search engine for [Goofish (闲鱼)](https://www.goofish.com) — China's largest second-hand marketplace. Works in **Guest mode** (no account) or **Full Access** via Alipay QR login.

## Features

- **Dual-mode search** — Bing web index (guest) or real-time Goofish API (authenticated)
- **Headless browser** — all background searches run silently, zero pop-ups
- **Alipay QR login** — optional; opens a visible window only for the QR scan
- **Auto translation** — English queries translated to Chinese via MyMemory API
- **Deal scoring** — items scored 0-100 based on price vs median
- **CNY → GBP conversion** — toggle dual-currency display
- **Saved deals** — heart any listing, persisted in SQLite
- **Anti-ban** — randomized 1.5-3.5s jitter, 15-min cache TTL, cooldown protection
- **Spam filtering** — hides junk listings (维修, 主板坏, 配件机, etc.)
- **Vinted-style UI** — polished dashboard with sidebar, category tabs, filters, detail drawer

## How It Works

### Guest Mode (No Account)
1. Type an English or Chinese query
2. Query is translated to Chinese via MyMemory API
3. Bing is searched for `site:goofish.com/item <query>` across 2 pages
4. Redirect links are followed to extract real item IDs
5. Titles, descriptions, and prices extracted from Bing snippets

### Full Access (Alipay Linked)
1. Click "Link Alipay Account" → scan QR code with Alipay app
2. Session cookies saved locally to `./data/session_state.json`
3. Searches use Goofish's internal `mtop` API for real-time results
4. Full product images, exact prices, seller info, 20+ results

## Architecture

```
Frontend (Tailwind CSS)  →  FastAPI Backend  →  Playwright Chromium (headless)
                                                  ↓
                              ┌─────────────────────────────────────┐
                              │ Connected? → mtop API (real-time)   │
                              │ Guest?     → Bing site: search      │
                              └─────────────────────────────────────┘
                                                  ↓
                              Deal scoring + GBP conversion + SQLite
```

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

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check + browser + session status |
| `/api/session/status` | GET | Guest / connected / expired |
| `/api/session/login` | POST | Open Alipay QR login window |
| `/api/session/logout` | POST | Clear session cookies |
| `/api/search?q=keyword` | GET | Dual-mode search (params: min_price, max_price, sort, category, filter_spam) |
| `/api/deals/save` | POST | Save a deal |
| `/api/deals/{item_id}` | DELETE | Remove saved deal |
| `/api/deals` | GET | List saved deals |

## Tests

```bash
# Unit tests (48 tests)
python -m pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_e2e.py -q

# E2E test (requires running server + Chromium)
python -m pytest tests/test_e2e.py -v
```

## Limitations

- **No product images in guest mode** — Goofish blocks item content without login
- **~10 results per query in guest mode** — limited by Bing's index of goofish.com
- **Price extraction is best-effort** — prices only appear in Bing snippet text

## Project Structure

```
backend/
  main.py           — FastAPI app + lifespan
  routes.py         — All API endpoints (search, session, deals)
  discovery.py      — Bing multi-page search + redirect following
  browser_engine.py — Playwright headless engine + session management
  translator.py     — English→Chinese via MyMemory API
  normalizer.py     — Price parsing, image URL cleaning
  currency.py       — CNY↔GBP conversion
  deals.py          — Deal scoring + SQLite saved deals
  cache.py          — In-memory TTL cache (15 min)
  config.py         — All settings (port, jitter, categories, spam keywords)
frontend/
  index.html        — Vinted-style dashboard (Tailwind CSS)
  app.js            — Search, cards, drawer, session, saved deals
tests/
  test_*.py         — 48 unit tests
  test_e2e.py       — Playwright E2E tests
data/               — (gitignored) session state + saved deals DB
```

## Tech Stack

- **Backend:** Python, FastAPI, Playwright, SQLite
- **Frontend:** HTML, Tailwind CSS, vanilla JavaScript
- **Testing:** pytest (48 unit tests)
