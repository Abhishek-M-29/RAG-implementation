import logging

from ragframework.llms.google_genai import GoogleGenAIProvider

logger = logging.getLogger(__name__)

LLM_PROVIDER_REGISTRY = {
    "google_genai": GoogleGenAIProvider,
}


def get_llm(settings):
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
    return connector.from_config(config)
