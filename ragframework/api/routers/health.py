import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ragframework.api.schemas import (
    ComponentHealthResponse,
    ConfigResponse,
    HealthResponse,
    ReadyResponse,
)
from ragframework.config import Settings, get_settings
from ragframework.llms.registry import get_llm
from ragframework.vectorstores.registry import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/v1/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.get("/v1/ready")
def ready(settings: Settings = Depends(get_settings)):
    try:
        vs = get_vector_store(settings)
        if not vs.health_check():
            logger.warning("Readiness check failed: vector store unhealthy")
            return JSONResponse(
                content=ReadyResponse(
                    status="not_ready",
                    detail="vector store unhealthy",
                    vector_store=ComponentHealthResponse(
                        status="not_ready",
                        detail="vector store unhealthy",
                    ),
                    llm=ComponentHealthResponse(status="ok"),
                ).model_dump(),
                status_code=503,
            )
    except Exception as exc:
        logger.warning("Readiness check failed: vector store error", extra={"error": str(exc)})
        return JSONResponse(
            content=ReadyResponse(
                status="not_ready",
                detail=f"vector store error: {exc}",
                vector_store=ComponentHealthResponse(
                    status="not_ready",
                    detail=f"vector store error: {exc}",
                ),
                llm=ComponentHealthResponse(status="ok"),
            ).model_dump(),
            status_code=503,
        )

    try:
        get_llm(settings)
    except Exception as exc:
        logger.warning("Readiness check failed: LLM unavailable", extra={"error": str(exc)})
        return JSONResponse(
            content=ReadyResponse(
                status="not_ready",
                detail=f"LLM unavailable: {exc}",
                vector_store=ComponentHealthResponse(status="ok"),
                llm=ComponentHealthResponse(
                    status="not_ready",
                    detail=f"LLM unavailable: {exc}",
                ),
            ).model_dump(),
            status_code=503,
        )

    return ReadyResponse(
        status="ok",
        vector_store=ComponentHealthResponse(status="ok"),
        llm=ComponentHealthResponse(status="ok"),
    )


@router.get("/v1/config", response_model=ConfigResponse)
def get_config(settings: Settings = Depends(get_settings)):
    return ConfigResponse(
        vector_store=settings.vector_store,
        llm_provider=settings.llm_provider,
        auth_enabled=settings.auth_enabled,
    )
