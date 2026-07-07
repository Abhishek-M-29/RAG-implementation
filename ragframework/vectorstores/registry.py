import logging
import threading

from ragframework.vectorstores.faiss_store import FaissStore

logger = logging.getLogger(__name__)

VECTOR_STORE_REGISTRY = {
    "faiss": FaissStore,
}

_vector_store_instance = None
_vector_store_lock = threading.Lock()


def get_vector_store(settings):
    global _vector_store_instance
    if _vector_store_instance is not None:
        return _vector_store_instance

    with _vector_store_lock:
        if _vector_store_instance is not None:
            return _vector_store_instance

        connector = VECTOR_STORE_REGISTRY.get(settings.vector_store)
        if connector is None:
            raise ValueError(
                f"Unknown vector_store '{settings.vector_store}'. "
                f"Available: {list(VECTOR_STORE_REGISTRY)}"
            )
        config = {**settings.vector_store_config}
        config.setdefault("timeout", settings.vector_store_timeout_seconds)
        logger.info(
            "Vector store resolved",
            extra={"provider": settings.vector_store},
        )
        _vector_store_instance = connector.from_config(config)
        return _vector_store_instance
