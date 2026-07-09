from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.notification_schema import NotificationResponse
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.services.notification_list_service import NotificationListService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/notifications",
    tags=["Notifications"],
)


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.get("", response_model=SuccessMessage)
async def list_notifications(
    workspace_id: UUID,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = NotificationListService(db)
        notifications = service.list_notifications(
            workspace_id,
            _user_id(current_user),
            unread_only=unread_only,
            limit=limit,
        )
        data = [
            NotificationResponse.model_validate(n).model_dump(mode="json")
            for n in notifications
        ]
        return SuccessMessage(
            message="Notifications retrieved successfully",
            data={"notifications": data},
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.patch("/{notification_id}/read", response_model=SuccessMessage)
async def mark_notification_read(
    workspace_id: UUID,
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = NotificationListService(db)
        notification = service.mark_as_read(
            workspace_id, notification_id, _user_id(current_user)
        )
        return SuccessMessage(
            message="Notification marked as read",
            data={
                "notification": NotificationResponse.model_validate(notification).model_dump(
                    mode="json"
                )
            },
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
