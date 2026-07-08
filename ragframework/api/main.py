import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ragframework.api.deps import limiter
from ragframework.config import Settings, get_settings, validate_config
from ragframework.observability.logging import configure_logging, request_id_var
from ragframework.observability.metrics import setup_metrics
from ragframework.observability.tracing import setup_tracing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    validate_config(settings)

    setup_tracing(
        service_name="ragframework",
        otel_exporter_endpoint=settings.otel_exporter_endpoint,
    )
    setup_metrics(
        service_name="ragframework",
        otel_exporter_endpoint=settings.otel_exporter_endpoint,
    )

    if settings.async_ingestion and not settings.redis_url:
        raise ValueError(
            "ASYNC_INGESTION=True requires Redis. "
            "Set REDIS_URL in your .env or set ASYNC_INGESTION=False "
            "for synchronous (zero-dependency) ingestion."
        )
    if (
        settings.cache_backend == "redis" or settings.memory_backend == "redis"
    ) and not settings.redis_url:
        raise ValueError(
            f"CACHE_BACKEND={settings.cache_backend!r}, "
            f"MEMORY_BACKEND={settings.memory_backend!r}, "
            "but REDIS_URL is not set. "
            "Provide a REDIS_URL or set both backends to 'memory'."
        )
    _setup_rag_tracing(settings)

    if settings.cache_backend == "redis":
        from ragframework.cache import get_cache
        get_cache(settings)
    if settings.memory_backend == "redis":
        from ragframework.memory import get_memory
        get_memory(settings)
    _warm_models(settings)
    yield


def _setup_rag_tracing(settings: Settings) -> None:
    provider = settings.rag_tracing_provider
    if provider == "none":
        return
    if provider == "langsmith":
        import os as _os
        if "LANGCHAIN_TRACING_V2" not in _os.environ:
            _os.environ["LANGCHAIN_TRACING_V2"] = "true"
        logger.info("RAG tracing enabled via LangSmith")
    elif provider == "langfuse":
        import os as _os
        if "LANGFUSE_ENABLED" not in _os.environ:
            _os.environ["LANGFUSE_ENABLED"] = "true"
        logger.info("RAG tracing enabled via Langfuse")


def _warm_models(settings: Settings) -> None:
    """Pre-load models at startup so the first request is fast.

    We inject the live embedding-model object directly into the
    vector-store config dict that ``get_vector_store`` will use,
    without mutating the shared ``Settings`` singleton.
    """
    from langchain_huggingface import HuggingFaceEmbeddings
    embedding_model = HuggingFaceEmbeddings(model_name=settings.embedding_model)

    # Build an augmented config that carries the pre-loaded model object.
    # We temporarily swap the vector_store_config for the duration of the
    # get_vector_store call so the singleton is initialised with the warm model.
    original_config = settings.vector_store_config
    warm_config = {
        **original_config,
        "embedding_model": embedding_model,
        "model_name": settings.embedding_model,
    }
    # Pydantic v2 allows mutation via model_config extra='ignore'; use object.__setattr__
    # to avoid triggering validators, then restore immediately after the singleton is built.
    object.__setattr__(settings, "vector_store_config", warm_config)
    try:
        from ragframework.llms.registry import get_llm
        from ragframework.vectorstores.registry import get_vector_store
        get_vector_store(settings)
        get_llm(settings)
    finally:
        object.__setattr__(settings, "vector_store_config", original_config)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RAG Framework",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(req_id)
        try:
            from opentelemetry import trace as otel_trace
            span = otel_trace.get_current_span()
            if span is not None and span.is_recording():
                span.set_attribute("request.id", req_id)
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)

    from ragframework.api.routers import health, ingestion, query
    app.include_router(query.router)
    app.include_router(ingestion.router)
    app.include_router(health.router)
    return app


app = create_app()
