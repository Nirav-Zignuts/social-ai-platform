import uuid
from datetime import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.enums import GeneratedPostStatus, NotificationChannel, NotificationType, PostReviewAction
from app.models.generated_post import GeneratedPost
from app.models.notification import Notification
from app.models.post_review import PostReview
from app.services.notification_service import notify_post_ready_for_review
from app.services.post_review_service import MAX_TOTAL_REGENERATIONS, PostReviewService
from app.services.scheduling import calculate_next_scheduled_time


@pytest.fixture
def post(db, workspace, user):
    p = GeneratedPost(
        workspace_id=workspace.id,
        generation_cycle_id=uuid.uuid4(),
        caption="Original caption",
        hashtags=["#test"],
        cta="Click",
        status=GeneratedPostStatus.PENDING_REVIEW.value,
        regenerate_count=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_notify_post_ready_for_review_creates_both_channels(db, workspace, post, user):
    with patch("app.services.notification_service.EmailService") as mock_email_cls:
        mock_email_cls.return_value.send_post_notification_email.return_value = None
        notify_post_ready_for_review(str(post.id))

    notifications = (
        db.query(Notification)
        .filter(Notification.post_id == post.id)
        .order_by(Notification.channel)
        .all()
    )
    assert len(notifications) == 2
    channels = {n.channel for n in notifications}
    assert channels == {NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value}

    for n in notifications:
        assert n.type == NotificationType.POST_READY_FOR_REVIEW.value
        expected_link = (
            f"{settings.FRONTEND_URL.rstrip('/')}/workspaces/{workspace.id}/posts/{post.id}/review"
        )
        assert n.payload["review_link"] == expected_link
        assert "message" in n.payload

    email = next(n for n in notifications if n.channel == NotificationChannel.EMAIL.value)
    assert email.sent_at is not None

    mock_email_cls.return_value.send_post_notification_email.assert_called_once()
    call_kwargs = mock_email_cls.return_value.send_post_notification_email.call_args.kwargs
    assert call_kwargs["recipient"] == user.email
    assert call_kwargs["full_name"] == user.full_name
    assert str(workspace.id) in call_kwargs["review_link"]
    assert str(post.id) in call_kwargs["review_link"]


def test_approve_sets_status_and_scheduled_for(db, workspace, user, post):
    service = PostReviewService(db)
    result = service.approve(workspace.id, post.id, user.id)

    assert result.status == GeneratedPostStatus.APPROVED.value
    assert result.scheduled_for is not None

    review = db.query(PostReview).filter(PostReview.post_id == post.id).one()
    assert review.action == PostReviewAction.APPROVE

    notification = (
        db.query(Notification)
        .filter(
            Notification.post_id == post.id,
            Notification.type == NotificationType.POST_APPROVED.value,
        )
        .one()
    )
    assert notification.channel == NotificationChannel.IN_APP.value


def test_approve_preserves_existing_scheduled_for(db, workspace, user, post):
    from datetime import datetime, timezone

    existing = datetime(2026, 12, 25, 12, 0, tzinfo=timezone.utc)
    post.scheduled_for = existing
    db.commit()

    service = PostReviewService(db)
    result = service.approve(workspace.id, post.id, user.id)
    assert result.scheduled_for == existing


def test_reject_is_terminal(db, workspace, user, post):
    service = PostReviewService(db)

    with patch(
        "app.services.post_review_service.resume_generation_for_regenerate"
    ) as mock_resume:
        result = service.reject(workspace.id, post.id, user.id, feedback="Not on brand")
        mock_resume.assert_not_called()

    assert result.status == GeneratedPostStatus.REJECTED.value
    review = db.query(PostReview).filter(PostReview.post_id == post.id).one()
    assert review.action == PostReviewAction.REJECT
    assert review.feedback == "Not on brand"


@patch("app.services.post_review_service.resume_generation_for_regenerate")
def test_regenerate_calls_graph_resume(mock_resume, db, workspace, user, post):
    mock_resume.return_value = None
    service = PostReviewService(db)

    result = service.regenerate(
        workspace.id, post.id, user.id, feedback="Make it shorter"
    )

    mock_resume.assert_called_once_with(
        str(post.generation_cycle_id), "Make it shorter"
    )
    assert result.id == post.id

    review = db.query(PostReview).filter(PostReview.post_id == post.id).one()
    assert review.action == PostReviewAction.REGENERATE
    assert review.feedback == "Make it shorter"


def test_regenerate_cap_rejected(db, workspace, user, post):
    post.regenerate_count = MAX_TOTAL_REGENERATIONS
    db.commit()

    service = PostReviewService(db)
    with pytest.raises(HTTPException) as exc:
        service.regenerate(workspace.id, post.id, user.id, feedback="Try again")

    assert exc.value.status_code == 400
    assert "edit the post manually" in exc.value.detail.lower()


def test_skip_sets_status(db, workspace, user, post):
    service = PostReviewService(db)
    result = service.skip(workspace.id, post.id, user.id)

    assert result.status == GeneratedPostStatus.SKIPPED.value
    review = db.query(PostReview).filter(PostReview.post_id == post.id).one()
    assert review.action == PostReviewAction.SKIP


def test_edit_approves_with_edited_content(db, workspace, user, post):
    service = PostReviewService(db)
    result = service.edit(
        workspace.id,
        post.id,
        user.id,
        caption="Edited caption",
        hashtags=["#new"],
        cta="Buy now",
    )

    assert result.status == GeneratedPostStatus.APPROVED.value
    assert result.caption == "Edited caption"
    assert result.hashtags == ["#new"]
    assert result.cta == "Buy now"
    assert result.scheduled_for is not None

    review = db.query(PostReview).filter(PostReview.post_id == post.id).one()
    assert review.action == PostReviewAction.EDIT
    assert review.edited_caption == "Edited caption"
    assert review.edited_hashtags == ["#new"]
    assert review.edited_cta == "Buy now"


def test_access_control_forbidden(db, workspace, other_user, post):
    service = PostReviewService(db)
    with pytest.raises(HTTPException) as exc:
        service.approve(workspace.id, post.id, other_user.id)
    assert exc.value.status_code == 403


def test_review_rows_are_append_only(db, workspace, user, post):
    service = PostReviewService(db)
    service.reject(workspace.id, post.id, user.id, feedback="first")
    post.status = GeneratedPostStatus.PENDING_REVIEW.value
    db.commit()
    service.skip(workspace.id, post.id, user.id)

    reviews = db.query(PostReview).filter(PostReview.post_id == post.id).all()
    assert len(reviews) == 2
    actions = {r.action for r in reviews}
    assert PostReviewAction.REJECT in actions
    assert PostReviewAction.SKIP in actions


def test_calculate_next_scheduled_time_uses_workspace_timezone(db, workspace):
    workspace.timezone = "America/New_York"
    workspace.preferred_post_time = time(9, 30)
    scheduled = calculate_next_scheduled_time(workspace)
    assert scheduled.tzinfo is not None
