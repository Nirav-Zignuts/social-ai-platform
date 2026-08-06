"""Admin custom notification broadcast orchestration."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.models.notification_broadcast import NotificationBroadcast
from app.models.user import User
from app.repositories.notification_broadcast import NotificationBroadcastRepository
from app.services.admin_action_service import log_admin_action


class AdminBroadcastService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationBroadcastRepository(db)

    def queue_broadcast(
        self,
        *,
        admin_id: UUID,
        title: str,
        body: str,
        deep_link: str | None = None,
        data: dict | None = None,
        reason: str,
    ) -> dict:
        title_clean = title.strip()
        body_clean = body.strip()
        if not title_clean or not body_clean:
            raise HTTPException(status_code=400, detail="title and body are required")

        audience = (
            self.db.query(User.id)
            .filter(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
                User.status == UserStatus.ACTIVE,
            )
            .count()
        )

        broadcast = NotificationBroadcast(
            admin_id=admin_id,
            title=title_clean,
            body=body_clean,
            deep_link=(deep_link or "").strip() or None,
            data=data or None,
            target="all_users",
            status="queued",
            in_app_created=0,
            push_success=0,
            push_failure=0,
        )
        broadcast = self.repo.add(broadcast)

        log_admin_action(
            self.db,
            admin_id=admin_id,
            action_type="notification_broadcast",
            target_type="notification_broadcast",
            target_id=broadcast.id,
            reason=reason,
            payload_snapshot={
                "title": title_clean,
                "body": body_clean,
                "deep_link": broadcast.deep_link,
                "data": data,
                "audience_estimate": audience,
            },
        )

        return {
            "broadcast_id": str(broadcast.id),
            "status": broadcast.status,
            "target": broadcast.target,
            "audience_estimate": audience,
            "title": broadcast.title,
            "body": broadcast.body,
            "deep_link": broadcast.deep_link,
        }

    def get_broadcast(self, broadcast_id: UUID) -> dict:
        broadcast = self.repo.get(broadcast_id)
        if not broadcast:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        return {
            "broadcast_id": str(broadcast.id),
            "status": broadcast.status,
            "target": broadcast.target,
            "title": broadcast.title,
            "body": broadcast.body,
            "deep_link": broadcast.deep_link,
            "data": broadcast.data,
            "in_app_created": broadcast.in_app_created,
            "push_success": broadcast.push_success,
            "push_failure": broadcast.push_failure,
            "error_summary": broadcast.error_summary,
            "created_at": broadcast.created_at.isoformat()
            if broadcast.created_at
            else None,
        }
