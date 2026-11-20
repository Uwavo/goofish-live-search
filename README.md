# Goofish Live Search

Login-free, real-time search dashboard for Goofish (Xianyu/闲鱼) listings. Search, filter, and browse public listings directly from your local machine — no account, no cookies, no paid APIs.

## How It Works

- **Playwright + Chromium** opens Goofish pages like a real browser
- **Network interception** captures search API responses (mtop JSON)
- **DOM scraping fallback** extracts results from rendered HTML
- **Slider CAPTCHA handling** attempts to solve Alibaba NC challenges automatically
- **SQLite cache** (10-min TTL) avoids redundant fetches
- **Adaptive rate limiter** backs off on 403/CAPTCHA responses

## Prerequisites

- Python 3.10+
- Windows/macOS/Linux

## Setup

```bash
# Clone and enter the project
git clone https://github.com/YOUR_USER/goofish-live-search.git
cd goofish-live-search

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Install Chromium browser for Playwright
playwright install chromium
```

## Run

```bash
python -m backend.main
```

Open http://localhost:8000 in your browser. Type a search query and hit Enter.

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Health check + browser status |
| `GET /api/search?q=keyword&min_price=10&max_price=100&sort=price_asc&page=1` | Search listings |
| `GET /api/item/{id}` | Item detail |

## Tests

```bash
# Unit tests (fast, no network)
pytest tests/test_normalizer.py tests/test_cache.py -v

# Live integration tests (hits real Goofish)
pytest tests/test_live.py -v -m live

# End-to-end UI tests
pytest tests/test_e2e.py -v -m e2e
```

## Important Notes

- The browser runs in **headed mode** (visible window) for best anti-detection compatibility
- Goofish's anti-bot system (Alibaba SM) may occasionally block requests — the tool handles this with automatic slider solving and rate limiting
- Results are cached for 10 minutes to reduce requests
- This tool is for personal, educational use only

## Tech Stack

- **Backend:** Python, FastAPI, Playwright, SQLite
- **Frontend:** HTML, Tailwind CSS, vanilla JavaScript
- **Testing:** pytest, pytest-asyncio
