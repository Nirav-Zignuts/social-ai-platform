from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class AdminActionLog(BaseEntity):
    __tablename__ = "admin_action_logs"

    admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admins.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    admin = relationship("Admin")
