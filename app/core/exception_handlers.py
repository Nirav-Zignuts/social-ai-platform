from typing import Any, Dict, List,Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError,StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.common.messages import ErrorMessage, ErrorMessages
from app.common.responses import ErrorResponse


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
    """
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return _error_response(status_code=exc.status_code, message=detail)