"""SlowAPI rate limiting setup and 429 response handling."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.common.messages import ErrorMessage, ErrorMessages
from app.core.config import settings


def _rate_limit_key(request: Request) -> str:
    """Rate-limit by client IP (honors X-Forwarded-For when behind a proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First hop is the original client when trusted proxy sets this header.
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    # Disabled: most routes return Pydantic models, not Response objects.
    # Enabling requires injecting `response: Response` on every limited endpoint.
    headers_enabled=False,
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Return standard ErrorMessage JSON for HTTP 429."""
    detail = getattr(exc, "detail", None) or str(exc)

    payload = ErrorMessage(
        message=ErrorMessages.RATE_LIMIT_EXCEEDED,
        code=429,
        details={
            "limit": detail,
            "path": request.url.path,
        },
    )
    return JSONResponse(status_code=429, content=payload.model_dump())
