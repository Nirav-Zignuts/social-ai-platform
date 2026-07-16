from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class PostInsightSnapshot(BaseEntity):
    """Append-only history of Instagram post metrics (multiple rows per post)."""

    __tablename__ = "post_insight_snapshots"
    __table_args__ = (
        Index("ix_post_insight_snapshots_post_fetched", "post_id", "fetched_at"),
        Index("ix_post_insight_snapshots_workspace_fetched", "workspace_id", "fetched_at"),
    )

    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    like_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saved_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shares_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    views: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_interactions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_visits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    post = relationship("GeneratedPost", back_populates="insight_snapshots")
    workspace = relationship("Workspace", back_populates="post_insight_snapshots")
