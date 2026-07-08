from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity
from app.core.enums import UserStatus


class User(BaseEntity):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[UserStatus] = mapped_column(
    Enum(UserStatus, name="user_status"),
    nullable=False,
    server_default=UserStatus.PENDING,
)

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    auth_providers = relationship(
    "UserAuthProvider",
    back_populates="user",
    cascade="all, delete-orphan",
)