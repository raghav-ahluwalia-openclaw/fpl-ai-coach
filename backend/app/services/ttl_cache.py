from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Hashable


@dataclass
class _CacheItem:
    value: Any
    expires_at: float


class TTLCache:
    """Small in-process TTL cache for read-heavy API endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[Hashable, _CacheItem] = {}

    def get(self, key: Hashable) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            if item.expires_at <= now:
                self._data.pop(key, None)
                return None
            return item.value

    def set(self, key: Hashable, value: Any, ttl_seconds: int) -> Any:
        expires_at = time.time() + max(1, ttl_seconds)
        with self._lock:
            self._data[key] = _CacheItem(value=value, expires_at=expires_at)
        return value

    def get_or_set(self, key: Hashable, builder, ttl_seconds: int):
        cached = self.get(key)
        if cached is not None:
            return cached
        value = builder()
        return self.set(key, value, ttl_seconds)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


api_ttl_cache = TTLCache()
