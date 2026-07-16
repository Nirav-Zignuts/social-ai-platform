from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.v1.schemas.analytics_schema import (
    AnalyticsOverviewResponse,
    AnalyticsPostsResponse,
    AnalyticsTrendResponse,
    ContentTypeBreakdownResponse,
    QualityCorrelationResponse,
)
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.services.analytics_service import AnalyticsService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/analytics",
    tags=["Analytics"],
)


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.get("/overview", response_model=SuccessMessage)
async def analytics_overview(
    workspace_id: UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = AnalyticsService(db)
        data = service.get_overview(workspace_id, _user_id(current_user), period)
        return SuccessMessage(
            message="Analytics overview retrieved successfully",
            data=AnalyticsOverviewResponse.model_validate(data).model_dump(mode="json"),
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get("/trend", response_model=SuccessMessage)
async def analytics_trend(
    workspace_id: UUID,
    metric: str = Query(..., pattern="^(followers|reach|engagement_rate)$"),
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = AnalyticsService(db)
        data = service.get_trend(workspace_id, _user_id(current_user), metric, period)
        return SuccessMessage(
            message="Analytics trend retrieved successfully",
            data=AnalyticsTrendResponse.model_validate(data).model_dump(mode="json"),
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get("/posts", response_model=SuccessMessage)
async def analytics_posts(
    workspace_id: UUID,
    sort_by: str = Query("published_at", pattern="^(engagement_rate|reach|published_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    content_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = AnalyticsService(db)
        data = service.list_posts(
            workspace_id,
            _user_id(current_user),
            sort_by=sort_by,
            order=order,
            content_type=content_type,
            limit=limit,
            offset=offset,
        )
        return SuccessMessage(
            message="Analytics posts retrieved successfully",
            data=AnalyticsPostsResponse.model_validate(data).model_dump(mode="json"),
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get("/content-type-breakdown", response_model=SuccessMessage)
async def analytics_content_type_breakdown(
    workspace_id: UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = AnalyticsService(db)
        data = service.content_type_breakdown(workspace_id, _user_id(current_user), period)
        return SuccessMessage(
            message="Content type breakdown retrieved successfully",
            data=ContentTypeBreakdownResponse.model_validate(data).model_dump(mode="json"),
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get("/quality-correlation", response_model=SuccessMessage)
async def analytics_quality_correlation(
    workspace_id: UUID,
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = AnalyticsService(db)
        data = service.quality_correlation(workspace_id, _user_id(current_user), period)
        return SuccessMessage(
            message="Quality correlation retrieved successfully",
            data=QualityCorrelationResponse.model_validate(data).model_dump(mode="json"),
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
