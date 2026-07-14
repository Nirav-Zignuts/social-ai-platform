from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import PublishingJobStatus
from app.integrations.meta.exceptions import MetaAPIError, MetaIntegrationError
from app.integrations.meta.service import MetaService
from app.models.generated_post import GeneratedPost
from app.models.post_insight import PostInsight
from app.models.publishing_job import PublishingJob
from app.publishing.token import get_valid_token

# Feed post metrics via Graph insights (IMAGE / CAROUSEL_ALBUM posts).
FEED_INSIGHT_METRICS = (
    "likes,comments,saved,shares,reach,views,total_interactions,profile_visits"
)


def _insight_value(metrics: dict[str, int | None], *keys: str) -> int | None:
    for key in keys:
        if key in metrics and metrics[key] is not None:
            return metrics[key]
    return None


class PostInsightService:
    def __init__(self, db: Session, meta_service: MetaService | None = None) -> None:
        self.db = db
        self.meta_service = meta_service or MetaService()

    def get_published_ig_media_id(self, post_id: UUID) -> str | None:
        job = (
            self.db.query(PublishingJob)
            .filter(
                PublishingJob.post_id == post_id,
                PublishingJob.status == PublishingJobStatus.PUBLISHED,
                PublishingJob.platform_post_id.is_not(None),
            )
            .order_by(PublishingJob.published_at.desc().nullslast())
            .first()
        )
        return job.platform_post_id if job else None

    def get_cached_insight(self, post_id: UUID) -> PostInsight | None:
        return self.db.query(PostInsight).filter(PostInsight.post_id == post_id).first()

    async def refresh_post_insights(self, post: GeneratedPost) -> PostInsight | None:
        """Fetch latest Meta metrics for a published post and upsert post_insights."""
        ig_media_id = self.get_published_ig_media_id(post.id)
        if not ig_media_id:
            return self.get_cached_insight(post.id)

        try:
            account = get_valid_token(self.db, post.workspace_id)
        except MetaIntegrationError:
            return self.get_cached_insight(post.id)

        like_count: int | None = None
        comments_count: int | None = None
        permalink: str | None = None
        insight_map: dict[str, int | None] = {}
        raw: dict = {}

        try:
            media = await self.meta_service.get_media_details(
                ig_media_id,
                account.access_token,
            )
            like_count = media.like_count
            comments_count = media.comments_count
            permalink = media.permalink
            raw["media"] = media.model_dump()
        except MetaAPIError as exc:
            raw["media_error"] = str(exc)

        try:
            insights = await self.meta_service.get_media_insights(
                ig_media_id,
                account.access_token,
                metrics=FEED_INSIGHT_METRICS,
            )
            insight_map = insights.as_map()
            raw["insights"] = [m.model_dump() for m in insights.data]
        except MetaAPIError as exc:
            # Insights need instagram_manage_insights; keep media counts if present.
            raw["insights_error"] = str(exc)

        if like_count is None:
            like_count = _insight_value(insight_map, "likes")
        if comments_count is None:
            comments_count = _insight_value(insight_map, "comments")

        now = datetime.now(timezone.utc)
        existing = self.get_cached_insight(post.id)
        payload = {
            "ig_media_id": ig_media_id,
            "permalink": permalink,
            "like_count": like_count,
            "comments_count": comments_count,
            "saved_count": _insight_value(insight_map, "saved"),
            "shares_count": _insight_value(insight_map, "shares"),
            "reach": _insight_value(insight_map, "reach"),
            "views": _insight_value(insight_map, "views"),
            "total_interactions": _insight_value(insight_map, "total_interactions"),
            "profile_visits": _insight_value(insight_map, "profile_visits"),
            "raw_metrics": raw,
            "fetched_at": now,
        }

        if existing:
            for key, value in payload.items():
                if key == "permalink" and value is None:
                    continue
                setattr(existing, key, value)
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        insight = PostInsight(
            post_id=post.id,
            workspace_id=post.workspace_id,
            **payload,
        )
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)
        return insight
