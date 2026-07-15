from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.onboarding_chat_message import OnboardingChatMessage
from app.models.onboarding_chat_session import OnboardingChatSession
from app.repositories.base import BaseRepository


class OnboardingChatSessionRepository(BaseRepository[OnboardingChatSession]):
    model = OnboardingChatSession

    def get_for_workspace(
        self, session_id: UUID, workspace_id: UUID
    ) -> Optional[OnboardingChatSession]:
        stmt = (
            select(self.model)
            .where(
                self.model.id == session_id,
                self.model.workspace_id == workspace_id,
                self.model.is_deleted.is_(False),
            )
            .options(selectinload(self.model.messages))
        )
        return self.db.execute(stmt).scalar_one_or_none()


class OnboardingChatMessageRepository(BaseRepository[OnboardingChatMessage]):
    model = OnboardingChatMessage

    def list_for_session(self, session_id: UUID) -> list[OnboardingChatMessage]:
        stmt = (
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.is_deleted.is_(False),
            )
            .order_by(self.model.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
