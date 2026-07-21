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
    """Rate-limit by IP; trust forwarding headers only when explicitly enabled."""
    forwarded = request.headers.get("X-Forwarded-For")
    if settings.TRUST_PROXY_HEADERS and forwarded:
        # Enable only when the deployment proxy overwrites, rather than appends
        # to, client-supplied X-Forwarded-For.
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
    payload = ErrorMessage(
        message=ErrorMessages.RATE_LIMIT_EXCEEDED,
        code=429,
        details=None,
    )
    return JSONResponse(status_code=429, content=payload.model_dump())
