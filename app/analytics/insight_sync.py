"""Periodic refresh of recent post insights + append-only snapshots."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.enums import GeneratedPostStatus, PublishingJobStatus
from app.db.session import SessionLocal
from app.models.generated_post import GeneratedPost
from app.models.publishing_job import PublishingJob
from app.services.post_insight_service import PostInsightService

logger = logging.getLogger(__name__)

RECENT_POST_DAYS = 14


async def _sync_insights_async() -> dict:
    db = SessionLocal()
    service = PostInsightService(db)
    synced = 0
    skipped = 0
    failed = 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_POST_DAYS)
        post_ids = (
            db.query(GeneratedPost.id)
            .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
            .filter(
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
                PublishingJob.status == PublishingJobStatus.PUBLISHED,
                PublishingJob.published_at.is_not(None),
                PublishingJob.published_at >= cutoff,
            )
            .group_by(GeneratedPost.id)
            .all()
        )

        for (post_id,) in post_ids:
            post = db.get(GeneratedPost, post_id)
            if not post:
                skipped += 1
                continue
            try:
                result = await service.refresh_post_insights(post, record_snapshot=True)
                if result:
                    synced += 1
                else:
                    skipped += 1
            except httpx.HTTPError as exc:
                failed += 1
                logger.warning(
                    "insight_sync network error post=%s: %r",
                    post_id,
                    exc,
                )
            except Exception as exc:
                failed += 1
                logger.warning(
                    "insight_sync failed post=%s: %s",
                    post_id,
                    exc or type(exc).__name__,
                    exc_info=True,
                )

        logger.info(
            "insight_sync complete synced=%s skipped=%s failed=%s total=%s",
            synced,
            skipped,
            failed,
            len(post_ids),
        )
        return {
            "status": "completed",
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "total": len(post_ids),
        }
    finally:
        db.close()


def sync_insights_for_recent_posts() -> dict:
    """Sync entry point for BackgroundTasks (sync wrapper)."""
    try:
        return asyncio.run(_sync_insights_async())
    except Exception as exc:
        logger.exception("insight_sync crashed")
        return {
            "status": "failed",
            "reason": str(exc) or type(exc).__name__,
            "synced": 0,
            "skipped": 0,
            "failed": 0,
            "total": 0,
        }


def poll_insight_sync() -> dict:
    """
    Queue a single job that refreshes insights for all recent published posts.

    Unlike publish/generation pollers, one background task processes all posts
    to avoid flooding BackgroundTasks with hundreds of Meta API calls.
    """
    return {"enqueued": 1, "run": "sync_insights_for_recent_posts"}
