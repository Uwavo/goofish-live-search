import os

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", "600"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT", "6"))
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT", "30000"))
NAVIGATION_TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT", "20000"))
SCROLL_DELAY_MS = int(os.getenv("SCROLL_DELAY", "2000"))
CACHE_DB_PATH = os.getenv("CACHE_DB", "cache.db")
SERVER_PORT = int(os.getenv("PORT", "1212"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

GOOFISH_BASE = "https://www.goofish.com"
GOOFISH_SEARCH_URL = f"{GOOFISH_BASE}/search?q={{query}}"
GOOFISH_ITEM_URL = f"{GOOFISH_BASE}/item/{{item_id}}"
