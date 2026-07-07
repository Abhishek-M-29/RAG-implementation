from ragframework.cache.base import BaseCache


class RedisCache(BaseCache):
    def __init__(self, redis_url: str):
        import redis

        self._client = redis.from_url(redis_url)

    def get(self, key: str) -> str | None:
        val = self._client.get(key)
        if val is None:
            return None
        return val.decode("utf-8") if isinstance(val, bytes) else val

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is not None:
            self._client.setex(key, ttl_seconds, value)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear(self) -> None:
        self._client.flushdb()
