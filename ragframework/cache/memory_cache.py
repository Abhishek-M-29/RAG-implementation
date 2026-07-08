import threading
import time

from cachetools import LRUCache

from ragframework.cache.base import BaseCache


class MemoryCache(BaseCache):
    """Thread-safe in-memory cache with per-item optional TTL.

    Items with an explicit TTL are stored with an expiry timestamp.
    Items without a TTL (e.g. embedding vectors) are stored permanently
    until evicted by LRU pressure.

    All operations are protected by a single ``threading.Lock``.
    """

    def __init__(self, maxsize: int = 1024):
        self._lock = threading.Lock()
        # LRU cache: evicts least-recently-used item when maxsize is exceeded
        self._cache: LRUCache = LRUCache(maxsize=maxsize)
        # Maps key → expiry timestamp (only keys with a TTL are present)
        self._expiries: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self._cache:
                return None
            expiry = self._expiries.get(key)
            if expiry is not None and time.monotonic() > expiry:
                # Expired — clean up both stores
                self._cache.pop(key, None)
                del self._expiries[key]
                return None
            return self._cache[key]  # type: ignore[return-value]

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        with self._lock:
            self._cache[key] = value
            if ttl_seconds is not None:
                self._expiries[key] = time.monotonic() + ttl_seconds
            else:
                # No TTL — remove any stale expiry entry
                self._expiries.pop(key, None)

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
            self._expiries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._expiries.clear()
