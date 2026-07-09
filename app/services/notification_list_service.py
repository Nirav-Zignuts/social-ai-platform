from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.messages import ErrorMessages
from app.models.notification import Notification
from app.models.workspace import Workspace


class NotificationListService:
    def __init__(self, db: Session):
        self.db = db

    def _get_workspace_or_403(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
        return workspace

    def list_notifications(
        self,
        workspace_id: UUID,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        self._get_workspace_or_403(workspace_id, user_id)

        query = (
            self.db.query(Notification)
            .filter(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
            )
            .order_by(Notification.created_at.desc())
        )

        if unread_only:
            query = query.filter(Notification.read_at.is_(None))

        return query.limit(limit).all()

    def mark_as_read(
        self,
        workspace_id: UUID,
        notification_id: UUID,
        user_id: UUID,
    ) -> Notification:
        self._get_workspace_or_403(workspace_id, user_id)

        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if not notification:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESOURCE_NOT_FOUND)

        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notification)

        return notification
