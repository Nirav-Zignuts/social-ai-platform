from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class BusinessProfile(BaseEntity):
    __tablename__ = "business_profiles"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prohibited_words: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    required_keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    workspace = relationship("Workspace", back_populates="business_profile")
