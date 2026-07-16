from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class ProfileMetricSnapshot(BaseEntity):
    """Historical Instagram profile metrics for a workspace (one row per sync)."""

    __tablename__ = "profile_metric_snapshots"
    __table_args__ = (
        Index("ix_profile_metric_snapshots_workspace_recorded", "workspace_id", "recorded_at"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    followers_count: Mapped[int] = mapped_column(Integer, nullable=False)
    follows_count: Mapped[int] = mapped_column(Integer, nullable=False)
    media_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    workspace = relationship("Workspace", back_populates="profile_metric_snapshots")
