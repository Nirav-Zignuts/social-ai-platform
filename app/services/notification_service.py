import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import NotificationChannel, NotificationType
from app.db.session import SessionLocal
from app.models.generated_post import GeneratedPost
from app.models.notification import Notification
from app.models.user import User
from app.models.workspace import Workspace
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

NOTIFICATION_MESSAGES = {
    NotificationType.POST_READY_FOR_REVIEW: "A new post is ready for your review.",
    NotificationType.POST_APPROVED: "Your post has been approved and scheduled.",
    NotificationType.POST_REJECTED: "Your post has been rejected.",
    NotificationType.POST_AUTO_APPROVED: (
        "A new post was auto-approved and scheduled, no action needed — "
        "review it anytime before it publishes."
    ),
}

EMAIL_SUBJECTS = {
    NotificationType.POST_READY_FOR_REVIEW: "A new post is ready for your review",
    NotificationType.POST_APPROVED: "Your post has been approved",
    NotificationType.POST_REJECTED: "Your post has been rejected",
    NotificationType.POST_AUTO_APPROVED: "A new post was auto-approved and scheduled",
}


def build_review_link(workspace_id: UUID, post_id: UUID) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/workspaces/{workspace_id}/posts/{post_id}/review"


def _build_payload(
    workspace_id: UUID,
    post_id: UUID | None,
    notification_type: NotificationType,
) -> dict:
    payload = {
        "message": NOTIFICATION_MESSAGES[notification_type],
    }
    if post_id is not None:
        payload["review_link"] = build_review_link(workspace_id, post_id)
    return payload


def create_notification(
    user_id: UUID,
    workspace_id: UUID,
    post_id: UUID | None,
    notification_type: NotificationType,
    channel: NotificationChannel,
    db: Session | None = None,
) -> Notification:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        notification = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            post_id=post_id,
            type=notification_type.value,
            channel=channel.value,
            payload=_build_payload(workspace_id, post_id, notification_type),
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)
        return notification
    finally:
        if owns_session:
            session.close()


def send_email_notification(notification: Notification, db: Session | None = None) -> None:
    """Send notification email to the user and mark the notification as sent."""
    owns_session = db is None
    session = db or SessionLocal()
    try:
        user = session.query(User).filter(User.id == notification.user_id).first()
        if not user or not user.email:
            logger.warning(
                "Skipping email notification %s: user %s not found or has no email",
                notification.id,
                notification.user_id,
            )
            return

        payload = notification.payload or {}
        message = payload.get("message", "You have a new notification.")
        review_link = payload.get("review_link")

        try:
            notification_type = NotificationType(notification.type)
            subject = EMAIL_SUBJECTS.get(notification_type, "New notification")
        except ValueError:
            subject = "New notification"

        EmailService().send_post_notification_email(
            recipient=user.email,
            full_name=user.full_name,
            subject=subject,
            message=message,
            review_link=review_link,
        )

        notification.sent_at = datetime.now(timezone.utc)
        session.add(notification)
        session.commit()
    except Exception:
        logger.exception(
            "Failed to send email notification %s to user %s",
            notification.id,
            notification.user_id,
        )
        raise
    finally:
        if owns_session:
            session.close()


def notify_post_ready_for_review(post_id: str) -> None:
    with SessionLocal() as db:
        post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
        if not post:
            return

        workspace = db.query(Workspace).filter(Workspace.id == post.workspace_id).first()
        if not workspace:
            return

        create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=post.id,
            notification_type=NotificationType.POST_READY_FOR_REVIEW,
            channel=NotificationChannel.IN_APP,
            db=db,
        )

        email_notification = create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=post.id,
            notification_type=NotificationType.POST_READY_FOR_REVIEW,
            channel=NotificationChannel.EMAIL,
            db=db,
        )
        send_email_notification(email_notification, db=db)


def notify_post_auto_approved(post_id: str) -> None:
    with SessionLocal() as db:
        post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
        if not post:
            return

        workspace = db.query(Workspace).filter(Workspace.id == post.workspace_id).first()
        if not workspace:
            return

        create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=post.id,
            notification_type=NotificationType.POST_AUTO_APPROVED,
            channel=NotificationChannel.IN_APP,
            db=db,
        )


def notify_post_approved(post_id: str, db: Session) -> None:
    post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
    if not post:
        return

    workspace = db.query(Workspace).filter(Workspace.id == post.workspace_id).first()
    if not workspace:
        return

    create_notification(
        user_id=workspace.owner_id,
        workspace_id=workspace.id,
        post_id=post.id,
        notification_type=NotificationType.POST_APPROVED,
        channel=NotificationChannel.IN_APP,
        db=db,
    )
