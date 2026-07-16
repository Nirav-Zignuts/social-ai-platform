from datetime import datetime, timezone
from uuid import UUID
import logging

import httpx
from sqlalchemy.orm import Session

from app.core.enums import PublishingJobStatus
from app.integrations.meta.exceptions import MetaAPIError, MetaIntegrationError
from app.integrations.meta.service import MetaService
from app.models.generated_post import GeneratedPost
from app.models.post_insight import PostInsight
from app.models.post_insight_snapshot import PostInsightSnapshot
from app.models.publishing_job import PublishingJob
from app.publishing.token import get_valid_token

# Feed post metrics via Graph insights (IMAGE / CAROUSEL_ALBUM posts).
# Likes/comments also come from GET /{media-id}?fields=like_count,comments_count.
# Insights require instagram_manage_insights — reconnect IG if account predates that scope.
FEED_INSIGHT_METRICS = (
    "likes,comments,saved,shares,reach,views,total_interactions,profile_visits"
)

INSIGHT_FIELD_LABELS = {
    "like_count": "Likes (media object)",
    "comments_count": "Comments (media object)",
    "saved_count": "Saves (insights)",
    "shares_count": "Shares (insights)",
    "reach": "Reach (insights)",
    "views": "Views (insights)",
    "total_interactions": "Interactions (insights)",
    "profile_visits": "Profile visits (insights)",
}

logger = logging.getLogger(__name__)


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

    async def refresh_post_insights(
        self,
        post: GeneratedPost,
        *,
        record_snapshot: bool = False,
    ) -> PostInsight | None:
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
            print(
                f"[insights] media object post={post.id} ig_media_id={ig_media_id} "
                f"media_type={media.media_type} "
                f"like_count={like_count} comments_count={comments_count}"
            )
        except MetaAPIError as exc:
            raw["media_error"] = str(exc)
            print(f"[insights] media API error post={post.id}: {exc}")
        except httpx.HTTPError as exc:
            logger.warning(
                "refresh_post_insights media network error post=%s: %r",
                post.id,
                exc,
            )
            raw["media_error"] = f"network_error: {type(exc).__name__}"
            return self.get_cached_insight(post.id)

        try:
            insight_map, insights_debug = await self.meta_service.fetch_media_insights_resilient(
                ig_media_id,
                account.access_token,
                metrics=FEED_INSIGHT_METRICS,
            )
            raw["insights"] = insights_debug
            raw["insights_map"] = insight_map
            print(
                f"[insights] insights API post={post.id} merged_map={insight_map} "
                f"attempts={insights_debug.get('attempts')}"
            )
            if insights_debug.get("per_metric_probes"):
                print(
                    f"[insights] per-metric probes post={post.id}: "
                    f"{insights_debug['per_metric_probes']}"
                )
        except MetaAPIError as exc:
            # Insights need instagram_manage_insights; keep media counts if present.
            raw["insights_error"] = str(exc)
            print(f"[insights] insights batch failed post={post.id}: {exc}")
        except httpx.HTTPError as exc:
            logger.warning(
                "refresh_post_insights insights network error post=%s: %r",
                post.id,
                exc,
            )
            raw["insights_error"] = f"network_error: {type(exc).__name__}"
            # Still persist media counts if we got them above.

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

        print(f"[insights] STORED post={post.id} workspace={post.workspace_id}")
        for field, label in INSIGHT_FIELD_LABELS.items():
            val = payload.get(field)
            status = "OK" if val is not None else "NULL (API omitted or scope/media-type)"
            print(f"  - {label}: {val} [{status}]")
        if raw.get("insights_error") or raw.get("media_error"):
            print(
                f"  - errors: media_error={raw.get('media_error')} "
                f"insights_error={raw.get('insights_error')}"
            )
        if not raw.get("insights_error") and not insight_map:
            print(
                "  - NOTE: empty insights map — reconnect Instagram to grant "
                "instagram_manage_insights, or wait up to 48h after publish."
            )
            try:
                debug_payload = await self.meta_service.debug_token(account.access_token)
                scopes = (debug_payload.get("data") or {}).get("scopes")
                print(f"  - token scopes from debug_token: {scopes}")
            except Exception as exc:
                print(f"  - debug_token failed: {exc}")

        if existing:
            for key, value in payload.items():
                if key == "permalink" and value is None:
                    continue
                setattr(existing, key, value)
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            insight = existing
        else:
            insight = PostInsight(
                post_id=post.id,
                workspace_id=post.workspace_id,
                **payload,
            )
            self.db.add(insight)
            self.db.commit()
            self.db.refresh(insight)

        if record_snapshot:
            snapshot = PostInsightSnapshot(
                post_id=post.id,
                workspace_id=post.workspace_id,
                like_count=payload["like_count"],
                comments_count=payload["comments_count"],
                saved_count=payload["saved_count"],
                shares_count=payload["shares_count"],
                reach=payload["reach"],
                views=payload["views"],
                total_interactions=payload["total_interactions"],
                profile_visits=payload["profile_visits"],
                fetched_at=now,
            )
            self.db.add(snapshot)
            self.db.commit()

        return insight
