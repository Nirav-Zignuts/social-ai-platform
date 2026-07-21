from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class Admin(BaseEntity):
    __tablename__ = "admins"
    __table_args__ = (
        UniqueConstraint("email", name="admins_email_key"),
        Index("ix_admins_email", "email", unique=True),
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    otp_codes = relationship(
        "AdminOTPCode",
        back_populates="admin",
        cascade="all, delete-orphan",
    )


class AdminOTPCode(BaseEntity):
    __tablename__ = "admin_otp_codes"

    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    consumed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    admin = relationship("Admin", back_populates="otp_codes")
