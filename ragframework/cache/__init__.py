import logging
import threading

import redis as redis_module

from ragframework.cache.base import BaseCache
from ragframework.cache.memory_cache import MemoryCache
from ragframework.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)

_index_fingerprint: int = 0
_fingerprint_lock = threading.Lock()

_FINGERPRINT_REDIS_KEY = "rag:index_fingerprint"


def index_fingerprint(redis_client: redis_module.Redis | None = None) -> int:
    if redis_client is not None:
        val = redis_client.get(_FINGERPRINT_REDIS_KEY)
        return int(val) if val is not None else 0
    global _index_fingerprint
    with _fingerprint_lock:
        return _index_fingerprint


def bump_index_fingerprint(redis_client: redis_module.Redis | None = None) -> None:
    if redis_client is not None:
        redis_client.incr(_FINGERPRINT_REDIS_KEY)
        return
    global _index_fingerprint
    with _fingerprint_lock:
        _index_fingerprint += 1


_cache_instance: BaseCache | None = None
_cache_lock = threading.Lock()


def get_cache(settings) -> BaseCache:
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    with _cache_lock:
        if _cache_instance is not None:
            return _cache_instance

        backend = settings.cache_backend
        if backend == "memory":
            _cache_instance = MemoryCache()
        elif backend == "redis":
            if not settings.redis_url:
                raise ValueError(
                    "CACHE_BACKEND=redis but REDIS_URL is not set. "
                    "Provide a REDIS_URL or set CACHE_BACKEND=memory."
                )
            _cache_instance = RedisCache(settings.redis_url)
        else:
            raise ValueError(f"Unknown cache_backend: {backend}")

        logger.info("Cache backend initialized", extra={"backend": backend})
        return _cache_instance


__all__ = [
    "BaseCache",
    "MemoryCache",
    "RedisCache",
    "get_cache",
    "index_fingerprint",
    "bump_index_fingerprint",
]
