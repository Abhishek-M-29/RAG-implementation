import logging
import threading

from ragframework.llms.google_genai import GoogleGenAIProvider

logger = logging.getLogger(__name__)

LLM_PROVIDER_REGISTRY = {
    "google_genai": GoogleGenAIProvider,
}

_llm_instance = None
_llm_lock = threading.Lock()


def get_llm(settings):
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    with _llm_lock:
        if _llm_instance is not None:
            return _llm_instance

        connector = LLM_PROVIDER_REGISTRY.get(settings.llm_provider)
        if connector is None:
            raise ValueError(
                f"Unknown llm_provider '{settings.llm_provider}'. "
                f"Available: {list(LLM_PROVIDER_REGISTRY)}"
            )
        config = {**settings.llm_config}
        config.setdefault("timeout", settings.llm_timeout_seconds)
        logger.info(
            "LLM provider resolved",
            extra={"provider": settings.llm_provider, "timeout": config.get("timeout")},
        )
        _llm_instance = connector.from_config(config)
        return _llm_instance
