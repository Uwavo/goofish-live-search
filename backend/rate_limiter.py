import asyncio
import time

from backend.config import RATE_LIMIT_PER_MINUTE


class AdaptiveRateLimiter:
    def __init__(self, max_per_minute: int = RATE_LIMIT_PER_MINUTE):
        self._interval = 60.0 / max_per_minute
        self._base_interval = self._interval
        self._max_interval = 60.0
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            wait = self._interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.time()

    def back_off(self) -> None:
        self._interval = min(self._interval * 2, self._max_interval)

    def reset(self) -> None:
        self._interval = self._base_interval


rate_limiter = AdaptiveRateLimiter()
