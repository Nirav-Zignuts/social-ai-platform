from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, text, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from app.common.models import BaseEntity
from app.core.enums import GeneratedPostStatus

class GeneratedPost(BaseEntity):
    __tablename__ = "generated_posts"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    generation_cycle_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True
    )
    content_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hashtags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    cta: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    status: Mapped[GeneratedPostStatus] = mapped_column(
        SQLEnum(GeneratedPostStatus, name="generated_post_status"),
        server_default=GeneratedPostStatus.DRAFT.value,
        default=GeneratedPostStatus.DRAFT,
        index=True
    )
    reviewer_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    regenerate_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="generated_posts")
    reviews = relationship("PostReview", back_populates="post", cascade="all, delete-orphan")
    publishing_jobs = relationship("PublishingJob", back_populates="post", cascade="all, delete-orphan")
