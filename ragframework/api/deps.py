import logging

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from ragframework.config import get_settings

logger = logging.getLogger(__name__)


def require_scope(required_scope: str):
    def _check(request: Request) -> None:
        settings = get_settings()
        if not settings.auth_enabled:
            return
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            logger.info(
                "Auth failure: missing or malformed Authorization header",
                extra={
                    "key_present": auth is not None,
                    "required_scope": required_scope,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )
        key = auth.removeprefix("Bearer ")
        key_scopes = settings.api_keys.get(key)
        if key_scopes is None:
            logger.info(
                "Auth failure: unrecognized API key",
                extra={
                    "key_present": True,
                    "key_valid": False,
                    "required_scope": required_scope,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        if required_scope not in key_scopes:
            logger.info(
                "Auth failure: key lacks required scope",
                extra={
                    "key_present": True,
                    "key_valid": True,
                    "required_scope": required_scope,
                    "key_scopes": key_scopes,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have '{required_scope}' scope",
            )

    # Give the dependency a unique name so FastAPI tracing/logs distinguish scopes
    _check.__name__ = f"require_scope_{required_scope}"
    return _check


def _rate_limit_key(request: Request) -> str:
    settings = get_settings()
    if settings.auth_enabled:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.removeprefix("Bearer ")
        return "unknown"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
