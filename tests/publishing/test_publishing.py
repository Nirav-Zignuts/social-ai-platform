import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.enums import (
    ConnectedAccountStatus,
    GeneratedPostStatus,
    NotificationChannel,
    NotificationType,
    PublishingJobStatus,
    SocialProvider,
)
from app.integrations.meta.exceptions import InstagramPublishError, MetaAPIError
from app.models.connected_account import ConnectedAccount
from app.models.generated_post import GeneratedPost
from app.models.notification import Notification
from app.models.publishing_job import PublishingJob
from app.publishing.service import find_due_post_ids, publish_post_to_instagram
from app.publishing.tasks import poll_due_posts, publish_post


def _make_post(db, workspace, *, status, scheduled_for, image_url="https://cdn.example.com/img.jpg"):
    post = GeneratedPost(
        workspace_id=workspace.id,
        generation_cycle_id=uuid.uuid4(),
        caption="Hello world",
        hashtags=["coffee", "#bloom"],
        cta="Visit us",
        image_url=image_url,
        status=status,
        scheduled_for=scheduled_for,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _make_connected_account(db, workspace, *, expires_at=None):
    account = ConnectedAccount(
        workspace_id=workspace.id,
        provider=SocialProvider.INSTAGRAM.value,
        provider_account_id="ig-123",
        provider_username="bloom_coffee",
        display_name="Bloom Coffee",
        access_token="page-token",
        expires_at=expires_at,
        page_id="page-1",
        instagram_business_account_id="17841400000000000",
        status=ConnectedAccountStatus.CONNECTED.value,
        connected_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_poller_finds_due_approved_posts(db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    future = datetime.now(timezone.utc) + timedelta(hours=2)

    due = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    not_due = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=future)
    pending = _make_post(db, workspace, status=GeneratedPostStatus.PENDING_REVIEW, scheduled_for=past)

    ids = find_due_post_ids(db)
    assert due.id in ids
    assert not_due.id not in ids
    assert pending.id not in ids


def test_poller_excludes_processing_and_published_jobs(db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    due = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    other = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)

    job = PublishingJob(
        post_id=due.id,
        workspace_id=workspace.id,
        scheduled_for=past,
        status=PublishingJobStatus.PROCESSING,
        attempt_count=1,
        platform="instagram",
    )
    db.add(job)
    db.commit()

    ids = find_due_post_ids(db)
    assert due.id not in ids
    assert other.id in ids


def test_poller_includes_retrying_jobs_for_next_attempt(db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    due = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    job = PublishingJob(
        post_id=due.id,
        workspace_id=workspace.id,
        scheduled_for=past,
        status=PublishingJobStatus.RETRYING,
        attempt_count=1,
        platform="instagram",
    )
    db.add(job)
    db.commit()

    assert due.id in find_due_post_ids(db)


def test_poller_excludes_future_scheduled_posts(db, workspace):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=future)
    assert post.id not in find_due_post_ids(db)


@patch("app.publishing.tasks.find_due_post_ids")
def test_poll_due_posts_returns_ids(mock_find, workspace):
    post_id = uuid.uuid4()
    mock_find.return_value = [post_id]

    fake_db = MagicMock()
    with patch("app.publishing.tasks.SessionLocal", return_value=fake_db):
        result = poll_due_posts()

    assert result["enqueued"] == 1
    assert result["post_ids"] == [str(post_id)]
    fake_db.close.assert_called_once()


@patch("app.publishing.service.asyncio.run")
def test_publish_happy_path(mock_run, db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    _make_connected_account(db, workspace)
    mock_run.return_value = "ig-media-999"

    result = publish_post_to_instagram(db, post.id, attempt_count=1)

    assert result["status"] == "published"
    assert result["ig_media_id"] == "ig-media-999"
    db.refresh(post)
    assert post.status == GeneratedPostStatus.PUBLISHED

    job = db.query(PublishingJob).filter(PublishingJob.post_id == post.id).one()
    assert job.status == PublishingJobStatus.PUBLISHED
    assert job.platform_post_id == "ig-media-999"


@patch("app.publishing.tasks.notify_token_expired")
def test_publish_token_expired_no_retry(mock_notify, db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    _make_connected_account(
        db,
        workspace,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    class SessionProxy:
        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            return None

        def get(self, *args, **kwargs):
            return db.get(*args, **kwargs)

        def query(self, *args, **kwargs):
            return db.query(*args, **kwargs)

    with patch("app.publishing.tasks.SessionLocal", return_value=SessionProxy()):
        result = publish_post(str(post.id))

    assert result["status"] == "token_expired"
    db.refresh(post)
    assert post.status == GeneratedPostStatus.APPROVED
    job = db.query(PublishingJob).filter(PublishingJob.post_id == post.id).one()
    assert job.status == PublishingJobStatus.FAILED
    assert "expired" in (job.last_error or "").lower()
    mock_notify.assert_called_once_with(str(workspace.id))


@patch("app.publishing.service.asyncio.run")
def test_publish_graph_failure_then_success_on_retry(mock_run, db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    _make_connected_account(db, workspace)

    mock_run.side_effect = [
        MetaAPIError(
            "temporary",
            status_code=500,
            response_body={"error": {"message": "temporary"}},
        ),
        "ig-media-ok",
    ]

    with pytest.raises(MetaAPIError):
        publish_post_to_instagram(db, post.id, attempt_count=1, will_retry=True)

    job = db.query(PublishingJob).filter(PublishingJob.post_id == post.id).one()
    assert job.status == PublishingJobStatus.RETRYING

    result = publish_post_to_instagram(db, post.id, attempt_count=2, will_retry=False)
    assert result["status"] == "published"
    db.refresh(post)
    assert post.status == GeneratedPostStatus.PUBLISHED


@patch("app.publishing.tasks.notify_publish_failed")
@patch("app.publishing.service.asyncio.run")
def test_publish_retry_exhaustion(mock_run, mock_notify_failed, db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    _make_connected_account(db, workspace)
    mock_run.side_effect = InstagramPublishError("boom")

    # Simulate two prior attempts already recorded.
    for attempt in (1, 2):
        db.add(
            PublishingJob(
                post_id=post.id,
                workspace_id=workspace.id,
                scheduled_for=past,
                status=PublishingJobStatus.RETRYING,
                attempt_count=attempt,
                platform="instagram",
            )
        )
    db.commit()

    class SessionProxy:
        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            return None

        def get(self, *args, **kwargs):
            return db.get(*args, **kwargs)

        def query(self, *args, **kwargs):
            return db.query(*args, **kwargs)

        def add(self, obj):
            return db.add(obj)

        def commit(self):
            return db.commit()

    with patch("app.publishing.tasks.SessionLocal", return_value=SessionProxy()):
        result = publish_post(str(post.id))

    assert result["status"] == "failed"
    db.refresh(post)
    assert post.status == GeneratedPostStatus.FAILED
    mock_notify_failed.assert_called_once()
    assert mock_notify_failed.call_args[0][0] == str(post.id)


def test_publish_race_skipped_status_clean_exit(db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.SKIPPED, scheduled_for=past)

    result = publish_post_to_instagram(db, post.id)
    assert result["status"] == "skipped"
    assert db.query(PublishingJob).filter(PublishingJob.post_id == post.id).count() == 0


@patch("app.publishing.service.asyncio.sleep", new_callable=AsyncMock)
@patch("app.publishing.service.MetaService")
def test_container_polling_timeout_is_retryable(mock_meta_cls, _sleep, db, workspace):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    post = _make_post(db, workspace, status=GeneratedPostStatus.APPROVED, scheduled_for=past)
    _make_connected_account(db, workspace)

    meta = MagicMock()
    mock_meta_cls.return_value = meta
    meta.create_image_container = AsyncMock(return_value=MagicMock(id="container-1"))
    meta.get_container_status = AsyncMock(
        return_value=MagicMock(status_code="IN_PROGRESS", status="processing")
    )

    with patch("app.publishing.service.CONTAINER_POLL_MAX_SECONDS", 0.01):
        with patch("app.publishing.service.CONTAINER_POLL_INTERVAL_SECONDS", 0):
            with pytest.raises(InstagramPublishError) as exc_info:
                publish_post_to_instagram(db, post.id, attempt_count=1, will_retry=True)

    assert "FINISHED" in str(exc_info.value)
    job = db.query(PublishingJob).filter(PublishingJob.post_id == post.id).one()
    assert job.status == PublishingJobStatus.RETRYING


@patch("app.services.notification_service.EmailService")
def test_notify_token_expired_creates_in_app_and_email(mock_email, db, workspace, user):
    from app.services.notification_service import notify_token_expired

    notify_token_expired(str(workspace.id))

    notes = (
        db.query(Notification)
        .filter(
            Notification.workspace_id == workspace.id,
            Notification.type == NotificationType.INSTAGRAM_TOKEN_EXPIRED.value,
        )
        .all()
    )
    channels = {n.channel for n in notes}
    assert NotificationChannel.IN_APP.value in channels
    assert NotificationChannel.EMAIL.value in channels
