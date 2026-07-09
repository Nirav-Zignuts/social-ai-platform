from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.common.messages import ErrorMessages
from app.core.enums import GeneratedPostStatus
from app.models.generated_post import GeneratedPost
from app.models.workspace import Workspace
from app.services.notification_service import build_review_link


class GeneratedPostService:
    def __init__(self, db: Session):
        self.db = db

    def _get_workspace_or_403(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
        return workspace

    def list_posts(
        self,
        workspace_id: UUID,
        user_id: UUID,
        status: str | None = None,
    ) -> list[GeneratedPost]:
        self._get_workspace_or_403(workspace_id, user_id)

        query = self.db.query(GeneratedPost).filter(
            GeneratedPost.workspace_id == workspace_id
        )

        if status:
            try:
                normalized = GeneratedPostStatus(status.upper()).value
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status filter: {status}",
                )
            query = query.filter(GeneratedPost.status == normalized)

        return query.order_by(GeneratedPost.created_at.desc()).all()

    def get_post(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> dict:
        self._get_workspace_or_403(workspace_id, user_id)

        post = (
            self.db.query(GeneratedPost)
            .options(joinedload(GeneratedPost.reviews))
            .filter(
                GeneratedPost.id == post_id,
                GeneratedPost.workspace_id == workspace_id,
            )
            .first()
        )
        if not post:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESOURCE_NOT_FOUND)

        return {
            "post": post,
            "review_link": build_review_link(workspace_id, post_id),
        }
