import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import GeneratedPostStatus, PublishingJobStatus, SocialProvider, WorkspaceStatus
from app.integrations.meta.exceptions import (
    InstagramContainerTimeoutError,
    InstagramPublishError,
    InstagramTokenExpiredError,
    MetaAPIError,
)
from app.integrations.meta.service import MetaService
from app.models.generated_post import GeneratedPost
from app.models.publishing_job import PublishingJob
from app.models.workspace import Workspace
from app.publishing.token import get_valid_token

logger = logging.getLogger(__name__)

CONTAINER_POLL_INTERVAL_SECONDS = 2
CONTAINER_POLL_MAX_SECONDS = 60


def build_instagram_caption(post: GeneratedPost) -> str:
    parts: list[str] = []
    if post.caption:
        parts.append(post.caption.strip())
    if post.cta:
        parts.append(post.cta.strip())
    if post.hashtags:
        tags = []
        for tag in post.hashtags:
            cleaned = tag.strip()
            if not cleaned:
                continue
            if not cleaned.startswith("#"):
                cleaned = f"#{cleaned.lstrip('#')}"
            tags.append(cleaned)
        if tags:
            parts.append(" ".join(tags))
    return "\n\n".join(parts)


def _meta_error_message(exc: Exception) -> str:
    if isinstance(exc, MetaAPIError):
        body = exc.response_body or {}
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            message = error.get("message") or str(exc)
            code = error.get("code")
            subcode = error.get("error_subcode")
            bits = [message]
            if code is not None:
                bits.append(f"code={code}")
            if subcode is not None:
                bits.append(f"subcode={subcode}")
            return " | ".join(bits)
        return str(exc)
    return str(exc)


def create_processing_job(
    db: Session,
    post: GeneratedPost,
    attempt_count: int,
) -> PublishingJob:
    scheduled_for = post.scheduled_for or datetime.now(timezone.utc)
    job = PublishingJob(
        post_id=post.id,
        workspace_id=post.workspace_id,
        scheduled_for=scheduled_for,
        status=PublishingJobStatus.PROCESSING,
        attempt_count=attempt_count,
        platform=SocialProvider.INSTAGRAM.value,
        last_error=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(db: Session, job: PublishingJob, error: str) -> None:
    job.status = PublishingJobStatus.FAILED
    job.last_error = error[:2000]
    db.add(job)
    db.commit()


def mark_job_retrying(db: Session, job: PublishingJob, error: str) -> None:
    """Keep the job out of the poller while Celery will retry."""
    job.status = PublishingJobStatus.RETRYING
    job.last_error = error[:2000]
    db.add(job)
    db.commit()


def mark_job_published(
    db: Session,
    job: PublishingJob,
    *,
    ig_media_id: str,
) -> None:
    job.status = PublishingJobStatus.PUBLISHED
    job.published_at = datetime.now(timezone.utc)
    job.platform_post_id = ig_media_id
    job.last_error = None
    db.add(job)
    db.commit()


async def _wait_for_container_finished(
    meta: MetaService,
    container_id: str,
    access_token: str,
) -> None:
    deadline = time.monotonic() + CONTAINER_POLL_MAX_SECONDS
    while time.monotonic() < deadline:
        status = await meta.get_container_status(container_id, access_token)
        code = (status.status_code or "").upper()
        logger.info("Instagram container %s status_code=%s", container_id, code)

        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            detail = status.status or code
            raise InstagramPublishError(f"Media container failed: {detail}")

        await asyncio.sleep(CONTAINER_POLL_INTERVAL_SECONDS)

    raise InstagramContainerTimeoutError(
        f"Media container {container_id} did not reach FINISHED within "
        f"{CONTAINER_POLL_MAX_SECONDS}s"
    )


async def _publish_to_instagram_async(
    *,
    ig_user_id: str,
    access_token: str,
    image_url: str,
    caption: str,
) -> str:
    meta = MetaService()
    container = await meta.create_image_container(
        ig_user_id,
        image_url=image_url,
        caption=caption,
        access_token=access_token,
    )
    await _wait_for_container_finished(meta, container.id, access_token)
    published = await meta.publish_container(
        ig_user_id,
        creation_id=container.id,
        access_token=access_token,
    )
    return published.id


def publish_post_to_instagram(
    db: Session,
    post_id: UUID,
    *,
    attempt_count: int = 1,
    will_retry: bool = False,
) -> dict:
    """
    Publish an approved post to Instagram.

    Returns a result dict with keys:
      - status: skipped | token_expired | published
      - job_id / ig_media_id when applicable
    Raises InstagramPublishError / MetaAPIError for retryable Graph failures.
    """
    post = db.get(GeneratedPost, post_id)
    if not post:
        logger.warning("publish_post: post %s not found", post_id)
        return {"status": "skipped", "reason": "post_not_found"}

    if post.status != GeneratedPostStatus.APPROVED:
        logger.info(
            "publish_post: post %s status=%s, exiting cleanly",
            post_id,
            post.status,
        )
        return {"status": "skipped", "reason": f"status_{post.status.value}"}

    if not post.image_url or not str(post.image_url).startswith("https://"):
        job = create_processing_job(db, post, attempt_count)
        error = (
            "Post image_url must be a public HTTPS URL for Instagram publishing. "
            f"Got: {post.image_url!r}"
        )
        if will_retry:
            mark_job_retrying(db, job, error)
        else:
            mark_job_failed(db, job, error)
        raise InstagramPublishError(error)

    job = create_processing_job(db, post, attempt_count)

    try:
        account = get_valid_token(db, post.workspace_id)
    except InstagramTokenExpiredError as exc:
        mark_job_failed(db, job, str(exc))
        return {"status": "token_expired", "job_id": str(job.id), "error": str(exc)}

    caption = build_instagram_caption(post)

    try:
        ig_media_id = asyncio.run(
            _publish_to_instagram_async(
                ig_user_id=account.instagram_business_account_id,
                access_token=account.access_token,
                image_url=post.image_url,
                caption=caption,
            )
        )
    except (MetaAPIError, InstagramPublishError) as exc:
        error = _meta_error_message(exc)
        if will_retry:
            mark_job_retrying(db, job, error)
        else:
            mark_job_failed(db, job, error)
        raise
    except Exception as exc:
        error = _meta_error_message(exc)
        if will_retry:
            mark_job_retrying(db, job, error)
        else:
            mark_job_failed(db, job, error)
        raise InstagramPublishError(error) from exc

    mark_job_published(db, job, ig_media_id=ig_media_id)
    post.status = GeneratedPostStatus.PUBLISHED
    db.add(post)
    db.commit()

    return {
        "status": "published",
        "job_id": str(job.id),
        "ig_media_id": ig_media_id,
    }


def find_due_post_ids(db: Session, *, now: datetime | None = None) -> list[UUID]:
    """Query approved posts that are due and not already processing/published.

    RETRYING jobs are intentionally eligible again so the next cron tick can
    re-attempt without Celery's in-process retry.
    """
    now = now or datetime.now(timezone.utc)

    active_jobs = (
        select(PublishingJob.post_id)
        .where(
            PublishingJob.status.in_(
                [
                    PublishingJobStatus.PROCESSING,
                    PublishingJobStatus.PUBLISHED,
                ]
            )
        )
        .scalar_subquery()
    )

    stmt = (
        select(GeneratedPost.id)
        .join(Workspace, Workspace.id == GeneratedPost.workspace_id)
        .where(
            GeneratedPost.status == GeneratedPostStatus.APPROVED,
            GeneratedPost.is_deleted.is_(False),
            GeneratedPost.scheduled_for.is_not(None),
            GeneratedPost.scheduled_for <= now,
            GeneratedPost.id.not_in(active_jobs),
            Workspace.is_deleted.is_(False),
            Workspace.status == WorkspaceStatus.ACTIVE.value,
        )
    )
    return list(db.execute(stmt).scalars().all())
