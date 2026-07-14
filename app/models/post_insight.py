from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class PostInsight(BaseEntity):
    """Cached Instagram engagement metrics for a published generated post."""

    __tablename__ = "post_insights"

    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_posts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ig_media_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    permalink: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    like_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saved_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shares_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    views: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_interactions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_visits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    raw_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    post = relationship("GeneratedPost", back_populates="insight")
