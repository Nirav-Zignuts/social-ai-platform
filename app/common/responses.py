"""
Standard response models for API endpoints.
"""

from typing import Generic, Optional, TypeVar
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response model."""
    model_config = {"extra": "forbid"}

    status: int = http_status.HTTP_200_OK
    message: str = "Operation completed successfully"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """Standard error response model."""
    model_config = {"extra": "forbid"}

    status: int = http_status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Unknown error occurred"
    data: Optional[dict] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model."""
    model_config = {"extra": "forbid"}

    items: Optional[T] = None
    total_items: int
    current_page: int
    page_size: int
    total_pages: int


class OffsetPaginationMeta(BaseModel):
    """Offset-style pagination block (page/limit/total_count + navigation flags)."""
    model_config = {"extra": "forbid"}

    page: int
    limit: int
    total_count: int
    total_pages: int
    has_next: bool
    has_prev: bool


class EventsPageData(BaseModel, Generic[T]):
    """Paginated list of events with nested ``pagination`` metadata."""
    model_config = {"extra": "forbid"}

    events: Optional[T] = None
    pagination: OffsetPaginationMeta


from fastapi.responses import JSONResponse


def error_response(
    message: str,
    status_code: int = http_status.HTTP_401_UNAUTHORIZED,
    data: Optional[dict] = None,
):
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            status=status_code,
            message=message,
            data=data,
        ).model_dump(),
    )


def success_response(
    message: str = "Operation completed successfully",
    status_code: int = http_status.HTTP_200_OK,
    data: Optional[dict] = None,
):
    return JSONResponse(
        status_code=status_code,
        content=SuccessResponse(
            status=status_code,
            message=message,
            data=data,
        ).model_dump(),
    )
