from datetime import time
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class Workspace(BaseEntity):
    __tablename__ = "workspaces"

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    preferred_post_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    require_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_status: Mapped[str] = mapped_column(String(30), default="workspace_created")
    status: Mapped[str] = mapped_column(String(20), default="active")

    owner = relationship("User")
    business_profile = relationship("BusinessProfile", back_populates="workspace", uselist=False, cascade="all, delete-orphan")
    knowledge_documents = relationship("KnowledgeDocument", back_populates="workspace", cascade="all, delete-orphan")
    ai_configuration = relationship("AIConfiguration", back_populates="workspace", uselist=False, cascade="all, delete-orphan")
