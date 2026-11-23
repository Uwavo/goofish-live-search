"""Deal scoring and saved deals persistence."""
import json
import sqlite3
import time
from statistics import median

from backend.config import SAVED_DEALS_DB


def compute_deal_score(price: float | None, all_prices: list[float]) -> int | None:
    """Score 0-100 based on how far below the median this price is."""
    if price is None or not all_prices or len(all_prices) < 2:
        return None
    med = median(all_prices)
    if med <= 0:
        return None
    ratio = price / med
    if ratio >= 1.0:
        return 0
    score = int((1.0 - ratio) * 100)
    return min(score, 100)


_initialized = False


def init_deals_db() -> None:
    import os
    global _initialized
    os.makedirs(os.path.dirname(SAVED_DEALS_DB), exist_ok=True)
    conn = sqlite3.connect(SAVED_DEALS_DB, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS saved_deals (
        item_id TEXT PRIMARY KEY,
        data TEXT,
        saved_at REAL
    )""")
    conn.commit()
    conn.close()
    _initialized = True


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SAVED_DEALS_DB, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def save_deal(item: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO saved_deals (item_id, data, saved_at) VALUES (?, ?, ?)",
            (item["id"], json.dumps(item, ensure_ascii=False), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_deal(item_id: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM saved_deals WHERE item_id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def get_saved_deals() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT data FROM saved_deals ORDER BY saved_at DESC"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        conn.close()


def get_saved_ids() -> set[str]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT item_id FROM saved_deals").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()
