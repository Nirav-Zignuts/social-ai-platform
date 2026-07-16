from typing import Any, Dict, List,Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError,StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.common.messages import ErrorMessage, ErrorMessages
from app.common.responses import ErrorResponse
from app.integrations.google.exceptions import (
    GoogleAPIError,
    GoogleIntegrationError,
    GoogleOAuthStateExpired,
    GoogleOAuthStateInvalid,
)
from app.integrations.meta.exceptions import (
    FacebookPageNotFound,
    InstagramAccountNotFound,
    MetaAPIError,
    MetaIntegrationError,
    OAuthStateExpired,
    OAuthStateInvalid,
)


def _format_error(err: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize a single pydantic error dict for client-friendly output
    return {
        "type": err.get("type"),
        "loc": err.get("loc"),
        "msg": err.get("msg"),
        "ctx": err.get("ctx", {}),
    }


async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors (422) and return `ErrorMessage` shape."""
    errors: List[Dict[str, Any]] = [_format_error(e) for e in exc.errors()]

    payload = ErrorMessage(
        message=ErrorMessages.INVALID_REQUEST,
        code=HTTP_422_UNPROCESSABLE_ENTITY,
        details=errors,
    )

    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle pydantic ValidationError raised outside the request parsing path."""
    errors: List[Dict[str, Any]] = [_format_error(e) for e in exc.errors()]

    payload = ErrorMessage(
        message=ErrorMessages.INVALID_REQUEST,
        code=HTTP_422_UNPROCESSABLE_ENTITY,
        details=errors,
    )

    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())

def _error_response(
    status_code: int,
    message: str,
    data: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """Build a JSONResponse from ErrorResponse shape."""
    body = ErrorResponse(
        status=status_code,
        message=message,
        data=data,
    ).model_dump()
    return JSONResponse(status_code=status_code, content=body)

def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle Starlette/FastAPI HTTPException (e.g. 404, 403 from framework).
    AppException and subclasses are handled by app_exception_handler when
    registered before this.
    RateLimitExceeded (429) is handled by rate_limit_exceeded_handler when registered.
    """
    if exc.status_code == 429:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        payload = ErrorMessage(
            message=ErrorMessages.RATE_LIMIT_EXCEEDED,
            code=429,
            details={"limit": detail},
        )
        return JSONResponse(status_code=429, content=payload.model_dump())

    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return _error_response(status_code=exc.status_code, message=detail)


async def meta_integration_exception_handler(
    _request: Request,
    exc: MetaIntegrationError,
) -> JSONResponse:
    if isinstance(exc, OAuthStateExpired):
        status_code = 400
    elif isinstance(exc, OAuthStateInvalid):
        status_code = 400
    elif isinstance(exc, InstagramAccountNotFound):
        status_code = 404
    elif isinstance(exc, FacebookPageNotFound):
        status_code = 404
    elif isinstance(exc, MetaAPIError):
        status_code = 502
    else:
        status_code = 400

    return _error_response(status_code=status_code, message=str(exc))


async def google_integration_exception_handler(
    _request: Request,
    exc: GoogleIntegrationError,
) -> JSONResponse:
    if isinstance(exc, (GoogleOAuthStateExpired, GoogleOAuthStateInvalid)):
        status_code = 400
    elif isinstance(exc, GoogleAPIError):
        status_code = 502
    else:
        status_code = 400

    return _error_response(status_code=status_code, message=str(exc))