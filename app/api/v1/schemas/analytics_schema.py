from pydantic import BaseModel, Field


class AnalyticsProfileSummary(BaseModel):
    followers: int | None = None
    followers_change: int | None = None
    followers_change_pct: float | None = None
    following: int | None = None
    post_count: int | None = None


class AnalyticsEngagementSummary(BaseModel):
    total_likes: int = 0
    total_comments: int = 0
    total_saves: int = 0
    total_shares: int = 0
    total_reach: int = 0
    avg_engagement_rate: float | None = None


class BestPerformingPost(BaseModel):
    post_id: str
    caption_preview: str
    engagement_rate: float
    image_url: str | None = None


class AnalyticsOverviewResponse(BaseModel):
    period: str
    profile: AnalyticsProfileSummary
    posts_published_in_period: int
    engagement: AnalyticsEngagementSummary
    best_performing_post: BestPerformingPost | None = None


class TrendDataPoint(BaseModel):
    date: str
    value: float | int


class AnalyticsTrendResponse(BaseModel):
    metric: str
    period: str
    data_points: list[TrendDataPoint]


class PostInsightsSummary(BaseModel):
    likes: int | None = None
    comments: int | None = None
    saves: int | None = None
    shares: int | None = None
    reach: int | None = None
    views: int | None = None
    profile_visitors: int | None = None
    engagement_rate: float | None = None


class AnalyticsPostItem(BaseModel):
    post_id: str
    caption_preview: str
    content_type: str | None = None
    published_at: str | None = None
    image_url: str | None = None
    insights: PostInsightsSummary | None = None


class AnalyticsPostsResponse(BaseModel):
    total: int
    posts: list[AnalyticsPostItem]


class ContentTypeBreakdownItem(BaseModel):
    content_type: str
    post_count: int
    avg_engagement_rate: float | None = None
    avg_reach: float | None = None


class ContentTypeBreakdownResponse(BaseModel):
    period: str
    breakdown: list[ContentTypeBreakdownItem]


class QualityCorrelationPoint(BaseModel):
    post_id: str
    reviewer_score: int
    engagement_rate: float


class QualityCorrelationResponse(BaseModel):
    period: str
    data_points: list[QualityCorrelationPoint]
    correlation_note: str | None = None
