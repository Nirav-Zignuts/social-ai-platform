import uuid

import pytest

from app.models.notification import Notification
from app.models.user import User
from app.services.notification_list_service import NotificationListService
from app.services.notification_service import create_notification
from app.core.enums import NotificationChannel, NotificationType


def test_list_and_mark_notifications_read(db, workspace, user):
    create_notification(
        user_id=user.id,
        workspace_id=workspace.id,
        post_id=None,
        notification_type=NotificationType.POST_AUTO_APPROVED,
        channel=NotificationChannel.IN_APP,
        db=db,
    )
    create_notification(
        user_id=user.id,
        workspace_id=workspace.id,
        post_id=None,
        notification_type=NotificationType.POST_APPROVED,
        channel=NotificationChannel.IN_APP,
        db=db,
    )

    service = NotificationListService(db)
    all_notifications = service.list_notifications(workspace.id, user.id)
    assert len(all_notifications) == 2

    unread = service.list_notifications(workspace.id, user.id, unread_only=True)
    assert len(unread) == 2

    marked = service.mark_as_read(workspace.id, unread[0].id, user.id)
    assert marked.read_at is not None

    remaining_unread = service.list_notifications(workspace.id, user.id, unread_only=True)
    assert len(remaining_unread) == 1


def test_notification_access_control(db, workspace, other_user):
    service = NotificationListService(db)
    with pytest.raises(Exception) as exc:
        service.list_notifications(workspace.id, other_user.id)
    assert getattr(exc.value, "status_code", None) == 403
