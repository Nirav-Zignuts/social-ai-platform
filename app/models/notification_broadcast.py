"""Admin-initiated notification broadcast jobs."""

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class NotificationBroadcast(BaseEntity):
    __tablename__ = "notification_broadcasts"

    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    deep_link: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    target: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    in_app_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    push_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    push_failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    admin = relationship("Admin")
