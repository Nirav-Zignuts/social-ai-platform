"""
Push notification fan-out.

Transactional events: send to the user's registered device tokens.
Broadcasts: prefer FCM topic for scale, then create in-app rows in batches.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import NotificationChannel, NotificationType
from app.db.session import SessionLocal
from app.integrations.firebase.fcm_client import get_fcm_client
from app.models.notification import Notification
from app.repositories.device_token import DeviceTokenRepository
from app.repositories.notification_broadcast import NotificationBroadcastRepository

logger = logging.getLogger(__name__)

PUSH_TITLES = {
    NotificationType.POST_READY_FOR_REVIEW: "Post ready for review",
    NotificationType.POST_REGENERATED: "Post regenerated",
    NotificationType.POST_APPROVED: "Post approved",
    NotificationType.POST_REJECTED: "Post rejected",
    NotificationType.POST_AUTO_APPROVED: "Post auto-approved",
    NotificationType.INSTAGRAM_TOKEN_EXPIRED: "Reconnect Instagram",
    NotificationType.POST_PUBLISH_FAILED: "Publish failed",
    NotificationType.POST_PUBLISH_SUCCEEDED: "Post published",
    NotificationType.BILLING_PAYMENT_FAILED: "Payment failed",
    NotificationType.BILLING_WORKSPACES_LOCKED: "Workspaces locked",
    NotificationType.ADMIN_BROADCAST: "Announcement",
}


def _stringify_data(payload: dict | None) -> dict[str, str]:
    data: dict[str, str] = {}
    for key, value in (payload or {}).items():
        if value is None:
            continue
        data[str(key)] = value if isinstance(value, str) else str(value)
    return data


def push_title_for(notification_type: str, payload: dict | None = None) -> str:
    if payload and payload.get("title"):
        return str(payload["title"])
    try:
        return PUSH_TITLES.get(
            NotificationType(notification_type),
            "New notification",
        )
    except ValueError:
        return "New notification"


def push_body_for(payload: dict | None) -> str:
    if not payload:
        return "You have a new notification."
    if payload.get("body"):
        return str(payload["body"])
    if payload.get("message"):
        return str(payload["message"])
    return "You have a new notification."


def build_push_data(notification: Notification) -> dict[str, str]:
    payload = dict(notification.payload or {})
    data = {
        "notification_id": str(notification.id),
        "type": notification.type,
        "channel": notification.channel,
        "user_id": str(notification.user_id),
    }
    if notification.workspace_id:
        data["workspace_id"] = str(notification.workspace_id)
    if notification.post_id:
        data["post_id"] = str(notification.post_id)

    for key in (
        "review_link",
        "settings_link",
        "billing_link",
        "deep_link",
        "workspace_name",
    ):
        if payload.get(key):
            data[key] = str(payload[key])

    # Prefer an explicit deep_link; else reuse first known link field.
    if "deep_link" not in data:
        for key in ("review_link", "settings_link", "billing_link"):
            if key in data:
                data["deep_link"] = data[key]
                break

    return data


def send_push_for_notification(
    notification: Notification,
    db: Session | None = None,
) -> None:
    """
    Deliver a push for an existing in-app notification.
    Never raises — push must not break generation/publish flows.
    """
    owns_session = db is None
    session = db or SessionLocal()
    try:
        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            return

        repo = DeviceTokenRepository(session)
        devices = repo.list_active_tokens_for_user(notification.user_id)
        tokens = [d.token for d in devices]
        if not tokens:
            return

        title = push_title_for(notification.type, notification.payload)
        body = push_body_for(notification.payload)
        data = build_push_data(notification)

        result = get_fcm_client().send_to_tokens(
            tokens,
            title=title,
            body=body,
            data=data,
        )
        if result.invalid_tokens:
            repo.deactivate_tokens(result.invalid_tokens)

        if result.success_count > 0 and notification.sent_at is None:
            notification.sent_at = datetime.now(timezone.utc)
            session.add(notification)
            session.commit()

        logger.info(
            "Push for notification %s: success=%s failure=%s invalid=%s",
            notification.id,
            result.success_count,
            result.failure_count,
            len(result.invalid_tokens),
        )
    except Exception:
        logger.exception(
            "Failed to send push for notification %s",
            getattr(notification, "id", None),
        )
    finally:
        if owns_session:
            session.close()


def send_push_to_user(
    user_id: UUID,
    *,
    title: str,
    body: str,
    data: dict | None = None,
    db: Session | None = None,
) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        repo = DeviceTokenRepository(session)
        tokens = [d.token for d in repo.list_active_tokens_for_user(user_id)]
        if not tokens:
            return {"success": 0, "failure": 0, "invalid": 0}

        result = get_fcm_client().send_to_tokens(
            tokens,
            title=title,
            body=body,
            data=_stringify_data(data),
        )
        if result.invalid_tokens:
            repo.deactivate_tokens(result.invalid_tokens)
        return {
            "success": result.success_count,
            "failure": result.failure_count,
            "invalid": len(result.invalid_tokens),
        }
    finally:
        if owns_session:
            session.close()


def process_notification_broadcast(broadcast_id: str) -> None:
    """
    Background worker: create in-app rows for all active users and fan out push.

    Always multicast to registered device tokens (reliable).
    Topic send is best-effort only — FCM reports topic success even with 0 subscribers.
    """
    with SessionLocal() as db:
        repo = NotificationBroadcastRepository(db)
        broadcast = repo.get(UUID(broadcast_id))
        if not broadcast:
            logger.error("Broadcast %s not found", broadcast_id)
            return

        broadcast.status = "processing"
        repo.save(broadcast)

        push_data = {
            "type": NotificationType.ADMIN_BROADCAST.value,
            "broadcast_id": str(broadcast.id),
            "title": broadcast.title,
            "body": broadcast.body,
        }
        if broadcast.deep_link:
            push_data["deep_link"] = broadcast.deep_link
        if broadcast.data:
            for key, value in broadcast.data.items():
                if value is not None and key not in push_data:
                    push_data[str(key)] = (
                        value if isinstance(value, str) else str(value)
                    )

        topic = (settings.FCM_ALL_USERS_TOPIC or "").strip()
        topic_ok = False
        if topic and settings.PUSH_NOTIFICATIONS_ENABLED:
            topic_ok = get_fcm_client().send_to_topic(
                topic,
                title=broadcast.title,
                body=broadcast.body,
                data=push_data,
            )

        push_success = 0
        push_failure = 0
        in_app_created = 0
        errors: list[str] = []

        try:
            for user_ids in repo.iter_active_user_ids(batch_size=500):
                rows = [
                    Notification(
                        user_id=user_id,
                        workspace_id=None,
                        post_id=None,
                        type=NotificationType.ADMIN_BROADCAST.value,
                        channel=NotificationChannel.IN_APP.value,
                        payload={
                            "title": broadcast.title,
                            "body": broadcast.body,
                            "message": broadcast.body,
                            "deep_link": broadcast.deep_link,
                            "broadcast_id": str(broadcast.id),
                            **(broadcast.data or {}),
                        },
                        sent_at=None,
                    )
                    for user_id in user_ids
                ]
                db.add_all(rows)
                db.commit()
                in_app_created += len(rows)

            # Always deliver via device tokens. Topic alone is not enough — FCM
            # accepts topic publishes with zero subscribers and still returns OK.
            if settings.PUSH_NOTIFICATIONS_ENABLED:
                device_repo = DeviceTokenRepository(db)
                offset = 0
                while True:
                    devices = device_repo.list_active_tokens(limit=500, offset=offset)
                    if not devices:
                        break
                    tokens = [d.token for d in devices]
                    result = get_fcm_client().send_to_tokens(
                        tokens,
                        title=broadcast.title,
                        body=broadcast.body,
                        data=push_data,
                    )
                    push_success += result.success_count
                    push_failure += result.failure_count
                    if result.invalid_tokens:
                        device_repo.deactivate_tokens(result.invalid_tokens)
                    offset += len(devices)

                if push_success > 0:
                    # Mark in-app rows as push-attempted/sent for this broadcast.
                    db.query(Notification).filter(
                        Notification.type == NotificationType.ADMIN_BROADCAST.value,
                        Notification.payload["broadcast_id"].astext == str(broadcast.id),
                    ).update(
                        {"sent_at": datetime.now(timezone.utc)},
                        synchronize_session=False,
                    )
                    db.commit()

            broadcast.in_app_created = in_app_created
            broadcast.push_success = push_success
            broadcast.push_failure = push_failure
            broadcast.status = "completed"
            if push_success == 0 and settings.PUSH_NOTIFICATIONS_ENABLED:
                broadcast.error_summary = (
                    "No successful device deliveries. Ensure clients called "
                    "/api/v1/devices/register after enabling notification permission."
                    + (" Topic publish OK but may have had 0 subscribers." if topic_ok else "")
                )
            else:
                broadcast.error_summary = None
            repo.save(broadcast)
            logger.info(
                "Broadcast %s completed in_app=%s topic=%s push_ok=%s push_fail=%s",
                broadcast_id,
                in_app_created,
                topic_ok,
                push_success,
                push_failure,
            )
        except Exception as exc:
            logger.exception("Broadcast %s failed", broadcast_id)
            errors.append(str(exc))
            broadcast.status = "failed"
            broadcast.in_app_created = in_app_created
            broadcast.push_success = push_success
            broadcast.push_failure = push_failure
            broadcast.error_summary = "; ".join(errors)[:2000]
            repo.save(broadcast)
