import logging
from uuid import UUID

from sqlalchemy import func

from app.core.enums import GeneratedPostStatus
from app.db.session import SessionLocal
from app.integrations.meta.exceptions import InstagramPublishError, MetaAPIError
from app.models.generated_post import GeneratedPost
from app.models.publishing_job import PublishingJob
from app.publishing.service import find_due_post_ids, publish_post_to_instagram
from app.services.notification_service import (
    notify_publish_failed,
    notify_publish_succeeded,
    notify_token_expired,
)

logger = logging.getLogger(__name__)

MAX_PUBLISH_ATTEMPTS = 3


def poll_due_posts() -> dict:
    """
    Find due approved posts. Caller should schedule publish_post via BackgroundTasks.
    """
    db = SessionLocal()
    try:
        due_ids = find_due_post_ids(db)
        post_ids = [str(pid) for pid in due_ids]
        logger.info("poll_due_posts found %s posts", len(post_ids))
        return {"enqueued": len(post_ids), "post_ids": post_ids}
    finally:
        db.close()


def _next_attempt_count(db, post_id: UUID) -> int:
    max_prev = (
        db.query(func.max(PublishingJob.attempt_count))
        .filter(PublishingJob.post_id == post_id)
        .scalar()
    )
    return int(max_prev or 0) + 1


def publish_post(post_id: str, *, bypass_attempt_cap: bool = False) -> dict:
    """
    Publish a single approved post to Instagram (two-step Graph API).

    Retries across cron ticks: transient failures leave the post APPROVED with a
    RETRYING job; the next poll re-queues until MAX_PUBLISH_ATTEMPTS.
    Token expiry does not retry.
    """
    db = SessionLocal()
    try:
        pid = UUID(post_id)
        attempt_count = _next_attempt_count(db, pid)
        if attempt_count > MAX_PUBLISH_ATTEMPTS and not bypass_attempt_cap:
            logger.warning(
                "publish_post: max attempts exceeded for %s (attempt=%s)",
                post_id,
                attempt_count,
            )
            return {"status": "failed", "error": "max_attempts_exceeded"}

        will_retry = (
            attempt_count < MAX_PUBLISH_ATTEMPTS and not bypass_attempt_cap
        )
        try:
            result = publish_post_to_instagram(
                db,
                pid,
                attempt_count=attempt_count,
                will_retry=will_retry,
            )

            if result["status"] == "skipped":
                return result

            if result["status"] == "token_expired":
                post = db.get(GeneratedPost, pid)
                if post:
                    notify_token_expired(str(post.workspace_id))
                return result

            notify_publish_succeeded(post_id)
            return result
        except (InstagramPublishError, MetaAPIError) as exc:
            if will_retry:
                logger.warning(
                    "publish_post attempt %s failed for %s (will retry on next poll): %s",
                    attempt_count,
                    post_id,
                    exc,
                )
                return {
                    "status": "retrying",
                    "attempt_count": attempt_count,
                    "error": str(exc),
                }

            post = db.get(GeneratedPost, pid)
            if post and post.status == GeneratedPostStatus.APPROVED:
                post.status = GeneratedPostStatus.FAILED
                db.add(post)
                db.commit()
            notify_publish_failed(post_id, str(exc))
            logger.error(
                "publish_post exhausted attempts for %s: %s",
                post_id,
                exc,
            )
            return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
