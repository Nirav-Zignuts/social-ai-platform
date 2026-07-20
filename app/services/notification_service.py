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
    NotificationType.INSTAGRAM_TOKEN_EXPIRED: (
        "Your Instagram connection has expired. Reconnect to resume publishing."
    ),
    NotificationType.POST_PUBLISH_FAILED: (
        "A scheduled post failed to publish after multiple attempts."
    ),
    NotificationType.POST_PUBLISH_SUCCEEDED: "Your scheduled post was published to Instagram.",
    NotificationType.BILLING_PAYMENT_FAILED: (
        "We could not process your subscription payment. "
        "Please update your payment method to avoid losing access."
    ),
}

EMAIL_SUBJECTS = {
    NotificationType.POST_READY_FOR_REVIEW: "A new post is ready for your review",
    NotificationType.POST_APPROVED: "Your post has been approved",
    NotificationType.POST_REJECTED: "Your post has been rejected",
    NotificationType.POST_AUTO_APPROVED: "A new post was auto-approved and scheduled",
    NotificationType.INSTAGRAM_TOKEN_EXPIRED: "Reconnect Instagram to resume publishing",
    NotificationType.POST_PUBLISH_FAILED: "A scheduled post failed to publish",
    NotificationType.POST_PUBLISH_SUCCEEDED: "Your post was published",
    NotificationType.BILLING_PAYMENT_FAILED: "Subscription payment failed",
}


def build_review_link(workspace_id: UUID, post_id: UUID) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/workspaces/{workspace_id}/posts/{post_id}"


def build_instagram_settings_link(workspace_id: UUID) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/workspaces/{workspace_id}/settings"


def build_billing_settings_link() -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/settings/billing"


def _build_payload(
    workspace_id: UUID,
    post_id: UUID | None,
    notification_type: NotificationType,
    extra: dict | None = None,
    *,
    workspace_name: str | None = None,
) -> dict:
    payload = {
        "message": NOTIFICATION_MESSAGES[notification_type],
    }
    if workspace_name:
        payload["workspace_name"] = workspace_name
    if notification_type == NotificationType.INSTAGRAM_TOKEN_EXPIRED:
        payload["settings_link"] = build_instagram_settings_link(workspace_id)
    elif notification_type == NotificationType.BILLING_PAYMENT_FAILED:
        payload["billing_link"] = build_billing_settings_link()
    elif post_id is not None:
        payload["review_link"] = build_review_link(workspace_id, post_id)
    if extra:
        payload.update(extra)
    return payload


def create_notification(
    user_id: UUID,
    workspace_id: UUID,
    post_id: UUID | None,
    notification_type: NotificationType,
    channel: NotificationChannel,
    db: Session | None = None,
    extra_payload: dict | None = None,
) -> Notification:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        workspace = (
            session.query(Workspace).filter(Workspace.id == workspace_id).first()
        )
        notification = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            post_id=post_id,
            type=notification_type.value,
            channel=channel.value,
            payload=_build_payload(
                workspace_id,
                post_id,
                notification_type,
                extra=extra_payload,
                workspace_name=workspace.name if workspace else None,
            ),
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

        payload = dict(notification.payload or {})
        if "workspace_name" not in payload:
            workspace = (
                session.query(Workspace)
                .filter(Workspace.id == notification.workspace_id)
                .first()
            )
            if workspace:
                payload["workspace_name"] = workspace.name

        message = payload.get("message", "You have a new notification.")
        review_link = (
            payload.get("review_link")
            or payload.get("settings_link")
            or payload.get("billing_link")
        )

        try:
            notification_type = NotificationType(notification.type)
            subject = EMAIL_SUBJECTS.get(notification_type, "New notification")
            type_value = notification_type.value
        except ValueError:
            subject = "New notification"
            type_value = notification.type

        EmailService().send_post_notification_email(
            recipient=user.email,
            full_name=user.full_name,
            subject=subject,
            message=message,
            review_link=review_link,
            notification_type=type_value,
            payload=payload,
        )

        notification.sent_at = datetime.now(timezone.utc)
        session.add(notification)
        session.commit()
    except Exception:
        # Never fail the parent workflow (generation/publish) because email failed.
        logger.exception(
            "Failed to send email notification %s to user %s",
            notification.id,
            notification.user_id,
        )
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


def notify_token_expired(workspace_id: str) -> None:
    with SessionLocal() as db:
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            return

        create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.INSTAGRAM_TOKEN_EXPIRED,
            channel=NotificationChannel.IN_APP,
            db=db,
        )
        email_notification = create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.INSTAGRAM_TOKEN_EXPIRED,
            channel=NotificationChannel.EMAIL,
            db=db,
        )
        send_email_notification(email_notification, db=db)


def notify_publish_failed(post_id: str, error_reason: str) -> None:
    with SessionLocal() as db:
        post = db.query(GeneratedPost).filter(GeneratedPost.id == post_id).first()
        if not post:
            return

        workspace = db.query(Workspace).filter(Workspace.id == post.workspace_id).first()
        if not workspace:
            return

        extra = {"error_reason": error_reason}
        create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=post.id,
            notification_type=NotificationType.POST_PUBLISH_FAILED,
            channel=NotificationChannel.IN_APP,
            db=db,
            extra_payload=extra,
        )
        email_notification = create_notification(
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            post_id=post.id,
            notification_type=NotificationType.POST_PUBLISH_FAILED,
            channel=NotificationChannel.EMAIL,
            db=db,
            extra_payload=extra,
        )
        send_email_notification(email_notification, db=db)


def notify_publish_succeeded(post_id: str) -> None:
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
            notification_type=NotificationType.POST_PUBLISH_SUCCEEDED,
            channel=NotificationChannel.IN_APP,
            db=db,
        )
