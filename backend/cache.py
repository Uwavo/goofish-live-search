import hashlib
import json
import sqlite3
import time
from typing import Any

from backend.config import CACHE_DB_PATH, CACHE_TTL_SECONDS

_write_count = 0


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, data TEXT, created_at REAL)"
    )
    return conn


def cache_key(endpoint: str, params: dict) -> str:
    raw = endpoint + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(key: str) -> Any | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT data, created_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        data, created_at = row
        if time.time() - created_at > CACHE_TTL_SECONDS:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None
        return json.loads(data)
    finally:
        conn.close()


def set_cached(key: str, data: Any) -> None:
    global _write_count
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), time.time()),
        )
        _write_count += 1
        if _write_count % 50 == 0:
            conn.execute(
                "DELETE FROM cache WHERE created_at < ?",
                (time.time() - CACHE_TTL_SECONDS,),
            )
        conn.commit()
    finally:
        conn.close()


def clear_cache() -> None:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM cache")
        conn.commit()
    finally:
        conn.close()
