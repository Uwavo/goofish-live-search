import os

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", "900"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT", "6"))
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT", "30000"))
NAVIGATION_TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT", "20000"))
SCROLL_DELAY_MS = int(os.getenv("SCROLL_DELAY", "2000"))
CACHE_DB_PATH = os.getenv("CACHE_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache.db"))
SERVER_PORT = int(os.getenv("PORT", "1212"))
SESSION_STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "session_state.json")
SAVED_DEALS_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "saved_deals.db")

CNY_TO_GBP_RATE = float(os.getenv("CNY_GBP_RATE", "0.11"))

REQUEST_JITTER_MIN = 1.5
REQUEST_JITTER_MAX = 3.5
COOLDOWN_SECONDS = 600

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

GOOFISH_BASE = "https://www.goofish.com"

SPAM_KEYWORDS = ["仅展示", "维修", "主板坏", "配件机", "不开机", "砖头机"]

CATEGORIES = {
    "all": "",
    "phones": "手机",
    "electronics": "数码",
    "computers": "电脑",
    "fashion": "服饰",
    "sneakers": "潮鞋",
    "cameras": "摄影",
    "gaming": "游戏",
    "home": "居家",
}
