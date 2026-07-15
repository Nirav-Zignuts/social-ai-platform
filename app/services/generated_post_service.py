from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.common.messages import ErrorMessages
from app.core.enums import GeneratedPostStatus
from app.integrations.meta.exceptions import InstagramTokenExpiredError, MetaAPIError
from app.integrations.meta.service import MetaService
from app.models.generated_post import GeneratedPost
from app.models.workspace import Workspace
from app.publishing.token import get_valid_token
from app.services.notification_service import build_review_link
from app.services.post_insight_service import PostInsightService


class GeneratedPostService:
    def __init__(self, db: Session):
        self.db = db
        self.insight_service = PostInsightService(db)
        self.meta_service = MetaService()

    def _get_workspace_or_403(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = (
            self.db.query(Workspace)
            .filter(
                Workspace.id == workspace_id,
                Workspace.is_deleted.is_(False),
            )
            .first()
        )
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

    async def soft_delete_post(
        self,
        workspace_id: UUID,
        post_id: UUID,
        user_id: UUID,
        *,
        sync_with_instagram: bool = False,
    ) -> dict:
        """
        Soft-delete a generated post.
        If sync_with_instagram and the post is published, delete IG media first,
        then soft-delete locally. Instagram failures abort local delete.
        """
        self._get_workspace_or_403(workspace_id, user_id)
        post = self._get_active_post(workspace_id, post_id)

        instagram_deleted = False
        instagram_skipped_reason: str | None = None
        ig_media_id: str | None = None

        if sync_with_instagram:
            if post.status != GeneratedPostStatus.PUBLISHED:
                instagram_skipped_reason = (
                    f"Post status is {post.status}; Instagram sync only applies to PUBLISHED posts"
                )
            else:
                ig_media_id = self.insight_service.get_published_ig_media_id(post.id)
                if not ig_media_id:
                    instagram_skipped_reason = (
                        "No Instagram media id found for this post; local soft-delete only"
                    )
                else:
                    try:
                        account = get_valid_token(self.db, workspace_id)
                        await self.meta_service.delete_media(
                            ig_media_id,
                            account.access_token,
                        )
                        instagram_deleted = True
                    except InstagramTokenExpiredError as exc:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Cannot sync delete to Instagram: {exc}. "
                                "Reconnect Instagram or retry with sync_with_instagram=false."
                            ),
                        ) from exc
                    except MetaAPIError as exc:
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                f"Instagram delete failed: {exc}. "
                                "Post was NOT deleted locally. Fix connection or retry."
                            ),
                        ) from exc

        post.is_deleted = True
        post.is_active = False
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        return {
            "post_id": str(post.id),
            "is_deleted": True,
            "sync_with_instagram": sync_with_instagram,
            "instagram_deleted": instagram_deleted,
            "ig_media_id": ig_media_id,
            "instagram_skipped_reason": instagram_skipped_reason,
        }

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
