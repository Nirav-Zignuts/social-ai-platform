from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_configuration import AIConfiguration
from app.models.business_profile import BusinessProfile
from app.models.knowledge_document import KnowledgeDocument
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    model = Workspace

    def get_by_slug(self, slug: str) -> Optional[Workspace]:
        stmt = select(self.model).where(self.model.slug == slug)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_user_workspaces(self, user_id: UUID) -> list[Workspace]:
        stmt = select(self.model).where(self.model.owner_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_owned_workspace(self, workspace_id: UUID, user_id: UUID) -> Optional[Workspace]:
        stmt = select(self.model).where(
            self.model.id == workspace_id,
            self.model.owner_id == user_id,
        )
        print(stmt)
        return self.db.execute(stmt).scalar_one_or_none()


class BusinessProfileRepository(BaseRepository[BusinessProfile]):
    model = BusinessProfile

    def get_by_workspace_id(self, workspace_id: UUID) -> Optional[BusinessProfile]:
        stmt = select(self.model).where(self.model.workspace_id == workspace_id)
        return self.db.execute(stmt).scalar_one_or_none()


class AIConfigurationRepository(BaseRepository[AIConfiguration]):
    model = AIConfiguration

    def get_by_workspace_id(self, workspace_id: UUID) -> Optional[AIConfiguration]:
        stmt = select(self.model).where(self.model.workspace_id == workspace_id)
        return self.db.execute(stmt).scalar_one_or_none()


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    model = KnowledgeDocument

    def get_by_workspace_id(self, workspace_id: UUID) -> list[KnowledgeDocument]:
        stmt = select(self.model).where(self.model.workspace_id == workspace_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_and_workspace(self, document_id: UUID, workspace_id: UUID) -> Optional[KnowledgeDocument]:
        stmt = select(self.model).where(
            self.model.id == document_id,
            self.model.workspace_id == workspace_id
        )
        return self.db.execute(stmt).scalar_one_or_none()
