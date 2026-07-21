from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostReviewResponse(BaseModel):
    id: UUID
    post_id: UUID
    reviewed_by: Optional[UUID]
    action: str
    feedback: Optional[str]
    edited_caption: Optional[str]
    edited_hashtags: Optional[list[str]]
    edited_cta: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeneratedPostResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    generation_cycle_id: UUID
    content_type: Optional[str]
    caption: Optional[str]
    hashtags: Optional[list[str]]
    cta: Optional[str]
    image_url: Optional[str]
    status: str
    reviewer_score: Optional[int]
    reviewer_notes: Optional[str]
    regenerate_count: int
    scheduled_for: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reviews: list[PostReviewResponse] = []

    model_config = ConfigDict(from_attributes=True)


class PostInsightResponse(BaseModel):
    ig_media_id: str
    permalink: Optional[str] = None
    like_count: Optional[int] = None
    comments_count: Optional[int] = None
    saved_count: Optional[int] = None
    shares_count: Optional[int] = None
    reach: Optional[int] = None
    views: Optional[int] = None
    total_interactions: Optional[int] = None
    profile_visits: Optional[int] = None
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeneratedPostDetailResponse(BaseModel):
    post: GeneratedPostResponse
    review_link: str
    insights: Optional[PostInsightResponse] = None


class RejectReviewRequest(BaseModel):
    feedback: Optional[str] = None


class RegenerateReviewRequest(BaseModel):
    feedback: str = Field(..., min_length=1)
    regenerate_image: bool = False


class EditReviewRequest(BaseModel):
    caption: str = Field(..., min_length=1)
    hashtags: Optional[list[str]] = None
    cta: Optional[str] = None
