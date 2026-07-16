"""Dashboard analytics aggregations."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.engagement import calculate_engagement_rate
from app.core.enums import GeneratedPostStatus, PublishingJobStatus
from app.generation.scheduler import get_workspace_local_now
from app.models.generated_post import GeneratedPost
from app.models.post_insight import PostInsight
from app.models.profile_metric_snapshot import ProfileMetricSnapshot
from app.models.publishing_job import PublishingJob
from app.models.workspace import Workspace
from app.repositories.workspace import WorkspaceRepository


VALID_PERIODS = frozenset({"7d", "30d", "90d"})
VALID_TREND_METRICS = frozenset({"followers", "reach", "engagement_rate"})
VALID_SORT_FIELDS = frozenset({"engagement_rate", "reach", "published_at"})
VALID_SORT_ORDERS = frozenset({"asc", "desc"})


def _order_expr(expr, order: str):
    """PostgreSQL requires DESC NULLS LAST, not NULLS LAST DESC."""
    if order == "desc":
        return expr.desc().nulls_last()
    return expr.asc().nulls_last()


def parse_period(period: str) -> timedelta:
    if period not in VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Use one of: 7d, 30d, 90d.",
        )
    return timedelta(days=int(period[:-1]))


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    delta = parse_period(period)
    end = datetime.now(timezone.utc)
    start = end - delta
    return start, end


def _published_at_subquery():
    return (
        func.max(PublishingJob.published_at)
        .filter(PublishingJob.status == PublishingJobStatus.PUBLISHED)
        .label("published_at")
    )


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)

    def _get_owned_workspace(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = self.workspace_repo.get_active_by_id(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return workspace

    def get_overview(self, workspace_id: UUID, user_id: UUID, period: str) -> dict:
        workspace = self._get_owned_workspace(workspace_id, user_id)
        start, end = _period_bounds(period)

        latest_profile = (
            self.db.query(ProfileMetricSnapshot)
            .filter(ProfileMetricSnapshot.workspace_id == workspace_id)
            .order_by(ProfileMetricSnapshot.recorded_at.desc())
            .first()
        )

        # Option B: day-over-day — latest vs most recent snapshot before today (local).
        local_today = get_workspace_local_now(workspace).date()
        tz = ZoneInfo(workspace.timezone or "UTC")
        today_start_utc = datetime.combine(local_today, time.min, tzinfo=tz).astimezone(
            timezone.utc
        )
        previous_day_profile = (
            self.db.query(ProfileMetricSnapshot)
            .filter(
                ProfileMetricSnapshot.workspace_id == workspace_id,
                ProfileMetricSnapshot.recorded_at < today_start_utc,
            )
            .order_by(ProfileMetricSnapshot.recorded_at.desc())
            .first()
        )

        followers_change = None
        followers_change_pct = None
        if latest_profile and previous_day_profile:
            followers_change = (
                latest_profile.followers_count - previous_day_profile.followers_count
            )
            if previous_day_profile.followers_count > 0:
                followers_change_pct = round(
                    followers_change / previous_day_profile.followers_count * 100,
                    2,
                )

        posts_published_in_period = (
            self.db.query(func.count(func.distinct(GeneratedPost.id)))
            .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
                PublishingJob.status == PublishingJobStatus.PUBLISHED,
                PublishingJob.published_at.is_not(None),
                PublishingJob.published_at >= start,
                PublishingJob.published_at <= end,
            )
            .scalar()
            or 0
        )

        insight_rows = (
            self.db.query(PostInsight, GeneratedPost)
            .join(GeneratedPost, GeneratedPost.id == PostInsight.post_id)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
                GeneratedPost.id.in_(
                    self.db.query(GeneratedPost.id)
                    .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
                    .filter(
                        GeneratedPost.workspace_id == workspace_id,
                        GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                        GeneratedPost.is_deleted.is_(False),
                        PublishingJob.status == PublishingJobStatus.PUBLISHED,
                        PublishingJob.published_at.is_not(None),
                        PublishingJob.published_at >= start,
                        PublishingJob.published_at <= end,
                    )
                    .distinct()
                ),
            )
            .all()
        )

        total_likes = sum((row[0].like_count or 0) for row in insight_rows)
        total_comments = sum((row[0].comments_count or 0) for row in insight_rows)
        total_saves = sum((row[0].saved_count or 0) for row in insight_rows)
        total_shares = sum((row[0].shares_count or 0) for row in insight_rows)
        total_reach = sum((row[0].reach or 0) for row in insight_rows)

        rates = []
        best_post = None
        best_rate = -1.0
        for insight, post in insight_rows:
            rate = calculate_engagement_rate(
                likes=insight.like_count,
                comments=insight.comments_count,
                saves=insight.saved_count,
                shares=insight.shares_count,
                reach=insight.reach,
            )
            if rate is not None:
                rates.append(rate)
                if rate > best_rate:
                    best_rate = rate
                    caption = post.caption or ""
                    best_post = {
                        "post_id": str(post.id),
                        "caption_preview": caption[:120],
                        "engagement_rate": rate,
                        "image_url": post.image_url,
                    }

        avg_engagement_rate = round(sum(rates) / len(rates), 2) if rates else None

        return {
            "period": period,
            "profile": {
                "followers": latest_profile.followers_count if latest_profile else None,
                "followers_change": followers_change,
                "followers_change_pct": followers_change_pct,
                "following": latest_profile.follows_count if latest_profile else None,
                "post_count": latest_profile.media_count if latest_profile else None,
            },
            "posts_published_in_period": posts_published_in_period,
            "engagement": {
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_saves": total_saves,
                "total_shares": total_shares,
                "total_reach": total_reach,
                "avg_engagement_rate": avg_engagement_rate,
            },
            "best_performing_post": best_post,
        }

    def get_trend(self, workspace_id: UUID, user_id: UUID, metric: str, period: str) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        if metric not in VALID_TREND_METRICS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric '{metric}'. Use: followers, reach, engagement_rate.",
            )
        start, end = _period_bounds(period)

        data_points: list[dict] = []

        if metric == "followers":
            rows = (
                self.db.query(ProfileMetricSnapshot)
                .filter(
                    ProfileMetricSnapshot.workspace_id == workspace_id,
                    ProfileMetricSnapshot.recorded_at >= start,
                    ProfileMetricSnapshot.recorded_at <= end,
                )
                .order_by(ProfileMetricSnapshot.recorded_at.asc())
                .all()
            )
            by_date: dict[date, int] = {}
            for row in rows:
                day = row.recorded_at.date()
                by_date[day] = row.followers_count
            data_points = [
                {"date": day.isoformat(), "value": value}
                for day, value in sorted(by_date.items())
            ]
        else:
            # Aggregate by publish day from publishing_jobs (one row per post via distinct publish).
            publish_day = func.date(PublishingJob.published_at).label("publish_day")
            engagement_expr = (
                (
                    func.coalesce(PostInsight.like_count, 0)
                    + func.coalesce(PostInsight.comments_count, 0)
                    + func.coalesce(PostInsight.saved_count, 0)
                    + func.coalesce(PostInsight.shares_count, 0)
                )
                * 100.0
                / func.nullif(PostInsight.reach, 0)
            )
            rows = (
                self.db.query(
                    publish_day,
                    func.sum(PostInsight.reach).label("total_reach"),
                    func.avg(engagement_expr).label("avg_rate"),
                )
                .select_from(GeneratedPost)
                .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
                .join(PostInsight, PostInsight.post_id == GeneratedPost.id)
                .filter(
                    GeneratedPost.workspace_id == workspace_id,
                    GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                    GeneratedPost.is_deleted.is_(False),
                    PublishingJob.status == PublishingJobStatus.PUBLISHED,
                    PublishingJob.published_at.is_not(None),
                    PublishingJob.published_at >= start,
                    PublishingJob.published_at <= end,
                )
                .group_by(func.date(PublishingJob.published_at))
                .order_by(func.date(PublishingJob.published_at).asc())
                .all()
            )
            for row in rows:
                if row.publish_day is None:
                    continue
                if metric == "reach":
                    if row.total_reach is None:
                        continue
                    data_points.append(
                        {"date": row.publish_day.isoformat(), "value": int(row.total_reach)}
                    )
                else:
                    if row.avg_rate is None:
                        continue
                    data_points.append(
                        {"date": row.publish_day.isoformat(), "value": round(float(row.avg_rate), 2)}
                    )

        return {"metric": metric, "period": period, "data_points": data_points}

    def list_posts(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        sort_by: str = "published_at",
        order: str = "desc",
        content_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        if sort_by not in VALID_SORT_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid sort_by '{sort_by}'.")
        if order not in VALID_SORT_ORDERS:
            raise HTTPException(status_code=400, detail=f"Invalid order '{order}'.")

        published_at = _published_at_subquery()
        engagement_expr = (
            (
                func.coalesce(PostInsight.like_count, 0)
                + func.coalesce(PostInsight.comments_count, 0)
                + func.coalesce(PostInsight.saved_count, 0)
                + func.coalesce(PostInsight.shares_count, 0)
            )
            * 100.0
            / func.nullif(PostInsight.reach, 0)
        )

        q = (
            self.db.query(
                GeneratedPost,
                published_at,
                PostInsight,
                engagement_expr.label("engagement_rate"),
            )
            .outerjoin(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
            .outerjoin(PostInsight, PostInsight.post_id == GeneratedPost.id)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
            )
            .group_by(GeneratedPost.id, PostInsight.id)
        )

        if content_type:
            q = q.filter(GeneratedPost.content_type == content_type)

        subq = q.subquery()
        total = self.db.query(func.count()).select_from(subq).scalar() or 0

        sort_col = {
            "published_at": published_at,
            "reach": func.max(PostInsight.reach),
            "engagement_rate": func.max(engagement_expr),
        }[sort_by]
        q = q.order_by(_order_expr(sort_col, order))

        rows = q.offset(offset).limit(limit).all()

        posts = []
        for post, pub_at, insight, rate in rows:
            caption = post.caption or ""
            insights_payload = None
            if insight:
                insights_payload = {
                    "likes": insight.like_count,
                    "comments": insight.comments_count,
                    "saves": insight.saved_count,
                    "shares": insight.shares_count,
                    "reach": insight.reach,
                    "views": insight.views,
                    "profile_visitors": insight.profile_visits,
                    "engagement_rate": (
                        round(float(rate), 2) if rate is not None else calculate_engagement_rate(
                            likes=insight.like_count,
                            comments=insight.comments_count,
                            saves=insight.saved_count,
                            shares=insight.shares_count,
                            reach=insight.reach,
                        )
                    ),
                }
            posts.append(
                {
                    "post_id": str(post.id),
                    "caption_preview": caption[:120],
                    "content_type": post.content_type,
                    "published_at": pub_at.isoformat() if pub_at else None,
                    "image_url": post.image_url,
                    "insights": insights_payload,
                }
            )

        return {"total": total, "posts": posts}

    def content_type_breakdown(
        self,
        workspace_id: UUID,
        user_id: UUID,
        period: str,
    ) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        start, end = _period_bounds(period)

        engagement_expr = (
            (
                func.coalesce(PostInsight.like_count, 0)
                + func.coalesce(PostInsight.comments_count, 0)
                + func.coalesce(PostInsight.saved_count, 0)
                + func.coalesce(PostInsight.shares_count, 0)
            )
            * 100.0
            / func.nullif(PostInsight.reach, 0)
        )

        rows = (
            self.db.query(
                GeneratedPost.content_type,
                func.count(func.distinct(GeneratedPost.id)).label("post_count"),
                func.avg(engagement_expr).label("avg_engagement_rate"),
                func.avg(PostInsight.reach).label("avg_reach"),
            )
            .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
            .outerjoin(PostInsight, PostInsight.post_id == GeneratedPost.id)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
                GeneratedPost.content_type.is_not(None),
                PublishingJob.status == PublishingJobStatus.PUBLISHED,
                PublishingJob.published_at.is_not(None),
                PublishingJob.published_at >= start,
                PublishingJob.published_at <= end,
            )
            .group_by(GeneratedPost.content_type)
            .having(func.count(func.distinct(GeneratedPost.id)) >= 1)
            .order_by(_order_expr(func.avg(engagement_expr), "desc"))
            .all()
        )

        breakdown = [
            {
                "content_type": row.content_type,
                "post_count": int(row.post_count),
                "avg_engagement_rate": (
                    round(float(row.avg_engagement_rate), 2)
                    if row.avg_engagement_rate is not None
                    else None
                ),
                "avg_reach": (
                    round(float(row.avg_reach), 2) if row.avg_reach is not None else None
                ),
            }
            for row in rows
        ]

        return {"period": period, "breakdown": breakdown}

    def quality_correlation(
        self,
        workspace_id: UUID,
        user_id: UUID,
        period: str,
    ) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        start, end = _period_bounds(period)

        rows = (
            self.db.query(GeneratedPost, PostInsight)
            .join(PublishingJob, PublishingJob.post_id == GeneratedPost.id)
            .outerjoin(PostInsight, PostInsight.post_id == GeneratedPost.id)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.status == GeneratedPostStatus.PUBLISHED,
                GeneratedPost.is_deleted.is_(False),
                GeneratedPost.reviewer_score.is_not(None),
                PublishingJob.status == PublishingJobStatus.PUBLISHED,
                PublishingJob.published_at.is_not(None),
                PublishingJob.published_at >= start,
                PublishingJob.published_at <= end,
            )
            .all()
        )

        data_points = []
        high_rates: list[float] = []
        low_rates: list[float] = []

        for post, insight in rows:
            rate = calculate_engagement_rate(
                likes=insight.like_count if insight else None,
                comments=insight.comments_count if insight else None,
                saves=insight.saved_count if insight else None,
                shares=insight.shares_count if insight else None,
                reach=insight.reach if insight else None,
            )
            if rate is None:
                continue
            data_points.append(
                {
                    "post_id": str(post.id),
                    "reviewer_score": post.reviewer_score,
                    "engagement_rate": rate,
                }
            )
            if post.reviewer_score >= 85:
                high_rates.append(rate)
            elif post.reviewer_score < 70:
                low_rates.append(rate)

        correlation_note = None
        if high_rates and low_rates:
            high_avg = round(sum(high_rates) / len(high_rates), 2)
            low_avg = round(sum(low_rates) / len(low_rates), 2)
            correlation_note = (
                f"Posts scoring 85+ averaged {high_avg}% engagement vs "
                f"{low_avg}% for posts scoring below 70"
            )

        return {
            "period": period,
            "data_points": data_points,
            "correlation_note": correlation_note,
        }
