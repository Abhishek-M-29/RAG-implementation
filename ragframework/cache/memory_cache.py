import time

from cachetools import Cache

from ragframework.cache.base import BaseCache


class MemoryCache(BaseCache):
    def __init__(self, maxsize: int = 1024):
        self._cache: Cache = Cache(maxsize=maxsize)
        self._ttls: dict[str, float] = {}

    def get(self, key: str) -> str | None:
        if key not in self._cache:
            return None
        expiry = self._ttls.get(key)
        if expiry is not None and time.monotonic() > expiry:
            del self._cache[key]
            del self._ttls[key]
            return None
        return self._cache[key]  # type: ignore[return-value]

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._cache[key] = value
        if ttl_seconds is not None:
            self._ttls[key] = time.monotonic() + ttl_seconds
        else:
            self._ttls.pop(key, None)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        self._ttls.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
        self._ttls.clear()
