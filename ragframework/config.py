import os
import logging

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    vector_store: Literal["faiss"] = "faiss"
    vector_store_config: dict = {"index_path": "index_store/faiss_index"}

    llm_provider: Literal["google_genai"] = "google_genai"
    llm_config: dict = {}

    chunk_size: int = 1000
    chunk_overlap: int = 100

    top_k: int = 5

    cache_backend: Literal["memory", "redis"] = "memory"
    memory_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = None

    query_cache_ttl: int = 3600

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    auth_enabled: bool = False
    api_keys: dict[str, list[str]] = {}
    query_rate_limit: str = "60/minute"
    ingestion_rate_limit: str = "10/minute"
    log_level: str = "INFO"
    log_raw_queries: bool = False

    object_storage_path: str = "uploads/"
    object_storage_timeout_seconds: float = 30.0
    async_ingestion: bool = False

    llm_timeout_seconds: float = 30.0
    vector_store_timeout_seconds: float = 30.0
    max_tokens_per_request: int = 4000

    cors_allowed_origins: list[str] = []
    max_upload_size_bytes: int = 50_000_000

    otel_exporter_endpoint: str | None = None
    rag_tracing_provider: Literal["none", "langsmith", "langfuse"] = "none"


def validate_config(settings: Settings) -> None:
    """Fail-fast startup validation.

    Checks every config value required by the *currently selected*
    connectors/backends and raises a clear, specific error (naming
    the missing variable) if anything required is absent.  Does not
    validate config for connectors that aren't selected.
    """
    # -- LLM provider --------------------------------------------------
    if settings.llm_provider == "google_genai":
        api_key = settings.llm_config.get("api_key")
        if not api_key:
            raise ValueError(
                "LLM_CONFIG__API_KEY is required when "
                "LLM_PROVIDER=google_genai. "
                "Set LLM_CONFIG__API_KEY in your .env or provide "
                "api_key in llm_config."
            )

    # -- Vector store --------------------------------------------------
    if settings.vector_store == "faiss":
        index_path = settings.vector_store_config.get("index_path", "index_store/faiss_index")
        parent = os.path.dirname(index_path) or "."
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError as exc:
                raise ValueError(
                    f"VECTOR_STORE_CONFIG__INDEX_PATH={index_path!r} "
                    f"parent directory cannot be created: {exc}"
                )

    # -- Redis-dependent backends --------------------------------------
    redis_required = []
    if settings.cache_backend == "redis":
        redis_required.append("CACHE_BACKEND=redis")
    if settings.memory_backend == "redis":
        redis_required.append("MEMORY_BACKEND=redis")
    if settings.async_ingestion:
        redis_required.append("ASYNC_INGESTION=true")
    if redis_required and not settings.redis_url:
        raise ValueError(
            f"REDIS_URL is required for: {', '.join(redis_required)}. "
            "Set REDIS_URL in your .env or switch affected backends to "
            "'memory' / set ASYNC_INGESTION=false."
        )

    logger.info(
        "Startup config validation passed",
        extra={
            "llm_provider": settings.llm_provider,
            "vector_store": settings.vector_store,
            "cache_backend": settings.cache_backend,
            "memory_backend": settings.memory_backend,
            "async_ingestion": settings.async_ingestion,
        },
    )
