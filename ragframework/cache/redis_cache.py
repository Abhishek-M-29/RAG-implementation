import redis

from ragframework.cache.base import BaseCache


class RedisCache(BaseCache):
    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self._client = redis.from_url(redis_url)
        self._default_ttl = default_ttl

    def get(self, key: str) -> str | None:
        val = self._client.get(key)
        if val is None:
            return None
        return val.decode("utf-8") if isinstance(val, bytes) else val

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._client.setex(key, ttl, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear(self) -> None:
        self._client.flushdb()
