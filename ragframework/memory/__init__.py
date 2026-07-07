import logging
import threading

from ragframework.memory.base import BaseSessionMemory
from ragframework.memory.in_memory import InMemorySessionMemory
from ragframework.memory.redis_memory import RedisSessionMemory

logger = logging.getLogger(__name__)

_memory_instance: BaseSessionMemory | None = None
_memory_lock = threading.Lock()


def get_memory(settings) -> BaseSessionMemory:
    global _memory_instance
    if _memory_instance is not None:
        return _memory_instance

    with _memory_lock:
        if _memory_instance is not None:
            return _memory_instance

        backend = settings.memory_backend
        if backend == "memory":
            _memory_instance = InMemorySessionMemory()
        elif backend == "redis":
            if not settings.redis_url:
                raise ValueError(
                    "MEMORY_BACKEND=redis but REDIS_URL is not set. "
                    "Provide a REDIS_URL or set MEMORY_BACKEND=memory."
                )
            _memory_instance = RedisSessionMemory(settings.redis_url)
        else:
            raise ValueError(f"Unknown memory_backend: {backend}")

        logger.info("Memory backend initialized", extra={"backend": backend})
        return _memory_instance


__all__ = [
    "BaseSessionMemory",
    "InMemorySessionMemory",
    "RedisSessionMemory",
    "get_memory",
]
