from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class AIConfiguration(BaseEntity):
    __tablename__ = "ai_configurations"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    content_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    caption_length: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hashtag_count: Mapped[int] = mapped_column(Integer, default=8)
    emoji_usage: Mapped[str] = mapped_column(String(20), default="moderate")
    cta_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workspace = relationship("Workspace", back_populates="ai_configuration")
