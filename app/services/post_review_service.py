from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.messages import ErrorMessages
from app.core.enums import GeneratedPostStatus, PostReviewAction, WorkspaceStatus
from app.models.generated_post import GeneratedPost
from app.models.post_review import PostReview
from app.models.workspace import Workspace
from app.services.generation.resume import (
    RegenerationCheckpointError,
    resume_generation_for_regenerate,
)
from app.services.notification_service import notify_post_approved
from app.services.scheduling import calculate_next_scheduled_time

# Running total across automated reviewer retries and human regenerations.
# When the cap is hit, users must edit manually instead of requesting more AI rewrites.
MAX_TOTAL_REGENERATIONS = 5


class PostReviewService:
    def __init__(self, db: Session):
        self.db = db

    def _get_workspace_or_403(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
        return workspace

    def _assert_workspace_active(self, workspace: Workspace) -> None:
        if workspace.status == WorkspaceStatus.LOCKED_OVER_LIMIT.value:
            raise HTTPException(
                status_code=403,
                detail=(
                    "This workspace is locked because it exceeds your plan limit. "
                    "Choose it as an active workspace in Billing, or upgrade your plan."
                ),
            )
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise HTTPException(
                status_code=403,
                detail=f"Workspace is not active (status={workspace.status}).",
            )

    def _get_post_or_404(self, workspace_id: UUID, post_id: UUID) -> GeneratedPost:
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

    def _insert_review(
        self,
        post: GeneratedPost,
        user_id: UUID,
        action: PostReviewAction,
        feedback: str | None = None,
        edited_caption: str | None = None,
        edited_hashtags: list[str] | None = None,
        edited_cta: str | None = None,
    ) -> PostReview:
        review = PostReview(
            post_id=post.id,
            reviewed_by=user_id,
            action=action,
            feedback=feedback,
            edited_caption=edited_caption,
            edited_hashtags=edited_hashtags,
            edited_cta=edited_cta,
        )
        self.db.add(review)
        self.db.flush()
        return review

    def approve(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> GeneratedPost:
        workspace = self._get_workspace_or_403(workspace_id, user_id)
        self._assert_workspace_active(workspace)
        post = self._get_post_or_404(workspace_id, post_id)

        self._insert_review(post, user_id, PostReviewAction.APPROVE)
        post.status = GeneratedPostStatus.APPROVED.value

        if post.scheduled_for is None:
            post.scheduled_for = calculate_next_scheduled_time(workspace)

        self.db.commit()
        self.db.refresh(post)

        notify_post_approved(str(post.id), self.db)
        return post

    def reject(
        self,
        workspace_id: UUID,
        post_id: UUID,
        user_id: UUID,
        feedback: str | None = None,
    ) -> GeneratedPost:
        self._get_workspace_or_403(workspace_id, user_id)
        post = self._get_post_or_404(workspace_id, post_id)

        self._insert_review(post, user_id, PostReviewAction.REJECT, feedback=feedback)
        post.status = GeneratedPostStatus.REJECTED.value

        self.db.commit()
        self.db.refresh(post)
        return post

    async def regenerate(
        self,
        workspace_id: UUID,
        post_id: UUID,
        user_id: UUID,
        feedback: str,
        regenerate_image: bool = False,
    ) -> GeneratedPost:
        workspace = self._get_workspace_or_403(workspace_id, user_id)
        self._assert_workspace_active(workspace)
        post = self._get_post_or_404(workspace_id, post_id)

        if post.regenerate_count >= MAX_TOTAL_REGENERATIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Maximum regeneration limit ({MAX_TOTAL_REGENERATIONS}) reached. "
                    "Please edit the post manually instead."
                ),
            )

        try:
            await resume_generation_for_regenerate(
                str(post.generation_cycle_id),
                feedback,
                regenerate_image=regenerate_image,
                expected_workspace_id=str(workspace.id),
                expected_post_id=str(post.id),
            )
        except RegenerationCheckpointError as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This post cannot be regenerated because its generation "
                    "checkpoint is missing or does not match the post."
                ),
            ) from exc

        self.db.expire(post)
        self.db.refresh(post)
        self._insert_review(post, user_id, PostReviewAction.REGENERATE, feedback=feedback)
        self.db.commit()
        self.db.refresh(post)
        return post

    def skip(self, workspace_id: UUID, post_id: UUID, user_id: UUID) -> GeneratedPost:
        self._get_workspace_or_403(workspace_id, user_id)
        post = self._get_post_or_404(workspace_id, post_id)

        self._insert_review(post, user_id, PostReviewAction.SKIP)
        post.status = GeneratedPostStatus.SKIPPED.value

        self.db.commit()
        self.db.refresh(post)
        return post

    def edit(
        self,
        workspace_id: UUID,
        post_id: UUID,
        user_id: UUID,
        caption: str,
        hashtags: list[str] | None = None,
        cta: str | None = None,
    ) -> GeneratedPost:
        workspace = self._get_workspace_or_403(workspace_id, user_id)
        post = self._get_post_or_404(workspace_id, post_id)

        self._insert_review(
            post,
            user_id,
            PostReviewAction.EDIT,
            edited_caption=caption,
            edited_hashtags=hashtags,
            edited_cta=cta,
        )

        post.caption = caption
        post.hashtags = hashtags
        post.cta = cta
        post.status = GeneratedPostStatus.APPROVED.value

        if post.scheduled_for is None:
            post.scheduled_for = calculate_next_scheduled_time(workspace)

        self.db.commit()
        self.db.refresh(post)
        return post
