from typing import Optional
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity
from app.core.enums import AuthProvider


class UserAuthProvider(BaseEntity):
    __tablename__ = "user_auth_providers"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider"),
        nullable=False,
    )

    provider_user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="auth_providers",
    )