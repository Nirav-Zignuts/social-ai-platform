"""
User session model for storing user session details.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class UserSession(BaseEntity):
    """User session model representing user sessions in the system."""

    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    auth_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    refresh_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    fcm_token: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )

    # Device and Platform Information
    platform: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    device_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    device_model: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    os_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    os_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    browser_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    browser_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Network and Device Identification
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Application Version
    app_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    user = relationship(
        "User",
        backref="sessions",
    )
