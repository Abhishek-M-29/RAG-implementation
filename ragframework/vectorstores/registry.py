import logging

from ragframework.vectorstores.faiss_store import FaissStore

logger = logging.getLogger(__name__)

VECTOR_STORE_REGISTRY = {
    "faiss": FaissStore,
}


def get_vector_store(settings):
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
    return connector.from_config(config)
