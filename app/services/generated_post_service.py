from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.common.messages import ErrorMessages
from app.core.enums import GeneratedPostStatus
from app.models.generated_post import GeneratedPost
from app.models.workspace import Workspace
from app.services.notification_service import build_review_link
from app.services.post_insight_service import PostInsightService


class GeneratedPostService:
    def __init__(self, db: Session):
        self.db = db
        self.insight_service = PostInsightService(db)

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
            GeneratedPost.workspace_id == workspace_id,
            GeneratedPost.is_deleted.is_(False),
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

    def _get_active_post(
        self, workspace_id: UUID, post_id: UUID
    ) -> GeneratedPost:
        post = (
            self.db.query(GeneratedPost)
            .filter(
                GeneratedPost.id == post_id,
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.is_deleted.is_(False),
            )
            .first()
        )
        if not post:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESOURCE_NOT_FOUND)
        return post

    async def get_post(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> dict:
        self._get_workspace_or_403(workspace_id, user_id)

        post = (
            self.db.query(GeneratedPost)
            .options(joinedload(GeneratedPost.reviews))
            .filter(
                GeneratedPost.id == post_id,
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.is_deleted.is_(False),
            )
            .first()
        )
        if not post:
            raise HTTPException(status_code=404, detail=ErrorMessages.RESOURCE_NOT_FOUND)

        insights = None
        if post.status == GeneratedPostStatus.PUBLISHED:
            insights = await self.insight_service.refresh_post_insights(post)
        else:
            insights = self.insight_service.get_cached_insight(post.id)

        return {
            "post": post,
            "review_link": build_review_link(workspace_id, post_id),
            "insights": insights,
        }

    def soft_delete_post(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> dict:
        self._get_workspace_or_403(workspace_id, user_id)
        post = self._get_active_post(workspace_id, post_id)

        post.is_deleted = True
        post.is_active = False
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return {"post_id": str(post.id), "is_deleted": True}

    def enqueue_publish_now(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> dict:
        self._get_workspace_or_403(workspace_id, user_id)

        post = self._get_active_post(workspace_id, post_id)

        if post.status != GeneratedPostStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only approved posts can be published. "
                    f"Current status: {post.status.value}"
                ),
            )

        # Actual publish is scheduled by the route via FastAPI BackgroundTasks.
        return {
            "post_id": str(post.id),
            "status": "queued",
        }
