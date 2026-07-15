from typing import Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class OnboardingChatMessage(BaseEntity):
    __tablename__ = "onboarding_chat_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quick_replies: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)

    session = relationship("OnboardingChatSession", back_populates="messages")
