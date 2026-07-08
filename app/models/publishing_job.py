from datetime import datetime
from typing import Optional
from sqlalchemy import String, text, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from app.common.models import BaseEntity
from app.core.enums import PublishingJobStatus

class PublishingJob(BaseEntity):
    __tablename__ = "publishing_jobs"

    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    status: Mapped[PublishingJobStatus] = mapped_column(
        SQLEnum(PublishingJobStatus, name="publishing_job_status"),
        server_default=PublishingJobStatus.QUEUED.value,
        default=PublishingJobStatus.QUEUED,
        index=True
    )
    
    attempt_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    platform: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    post = relationship("GeneratedPost", back_populates="publishing_jobs")
    # belongs to Workspace (no back-reference needed on Workspace for publishing jobs)
    workspace = relationship("Workspace")
