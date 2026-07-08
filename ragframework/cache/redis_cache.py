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
        # Delete only cache-owned key prefixes — do NOT use flushdb() as that
        # would also wipe session history (session:*) and the index fingerprint.
        for prefix in ("query:*", "emb:*"):
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=prefix, count=200)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
