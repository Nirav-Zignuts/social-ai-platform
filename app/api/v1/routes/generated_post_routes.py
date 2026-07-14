from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.v1.schemas.generated_post_schema import (
    EditReviewRequest,
    GeneratedPostResponse,
    PostInsightResponse,
    RegenerateReviewRequest,
    RejectReviewRequest,
)
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage, WorkspaceMessages
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.publishing.tasks import publish_post
from app.services.generated_post_service import GeneratedPostService
from app.services.post_review_service import PostReviewService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/generated-posts",
    tags=["Generated Posts"],
)


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.get("", response_model=SuccessMessage)
async def list_generated_posts(
    workspace_id: UUID,
    status: str | None = Query(None, description="Filter by post status"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = GeneratedPostService(db)
        posts = service.list_posts(workspace_id, _user_id(current_user), status=status)
        data = [
            GeneratedPostResponse.model_validate(p).model_dump(mode="json") for p in posts
        ]
        return SuccessMessage(
            message="Generated posts retrieved successfully",
            data={"posts": data},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get("/{post_id}", response_model=SuccessMessage)
async def get_generated_post(
    workspace_id: UUID,
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = GeneratedPostService(db)
        result = await service.get_post(workspace_id, post_id, _user_id(current_user))
        post_data = GeneratedPostResponse.model_validate(result["post"]).model_dump(
            mode="json"
        )
        insights = result.get("insights")
        return SuccessMessage(
            message="Generated post retrieved successfully",
            data={
                "post": post_data,
                "review_link": result["review_link"],
                "insights": (
                    PostInsightResponse.model_validate(insights).model_dump(mode="json")
                    if insights
                    else None
                ),
            },
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/review/approve", response_model=SuccessMessage)
async def approve_post(
    workspace_id: UUID,
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = PostReviewService(db)
        post = service.approve(workspace_id, post_id, _user_id(current_user))
        return SuccessMessage(
            message="Post approved successfully",
            data={"post": GeneratedPostResponse.model_validate(post).model_dump(mode="json")},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/review/reject", response_model=SuccessMessage)
async def reject_post(
    workspace_id: UUID,
    post_id: UUID,
    payload: RejectReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = PostReviewService(db)
        post = service.reject(
            workspace_id, post_id, _user_id(current_user), feedback=payload.feedback
        )
        return SuccessMessage(
            message="Post rejected successfully",
            data={"post": GeneratedPostResponse.model_validate(post).model_dump(mode="json")},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/review/regenerate", response_model=SuccessMessage)
async def regenerate_post(
    workspace_id: UUID,
    post_id: UUID,
    payload: RegenerateReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = PostReviewService(db)
        post = service.regenerate(
            workspace_id, post_id, _user_id(current_user), feedback=payload.feedback
        )
        return SuccessMessage(
            message="Post regeneration started",
            data={"post": GeneratedPostResponse.model_validate(post).model_dump(mode="json")},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/review/skip", response_model=SuccessMessage)
async def skip_post(
    workspace_id: UUID,
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = PostReviewService(db)
        post = service.skip(workspace_id, post_id, _user_id(current_user))
        return SuccessMessage(
            message="Post skipped successfully",
            data={"post": GeneratedPostResponse.model_validate(post).model_dump(mode="json")},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/review/edit", response_model=SuccessMessage)
async def edit_post(
    workspace_id: UUID,
    post_id: UUID,
    payload: EditReviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = PostReviewService(db)
        post = service.edit(
            workspace_id,
            post_id,
            _user_id(current_user),
            caption=payload.caption,
            hashtags=payload.hashtags,
            cta=payload.cta,
        )
        return SuccessMessage(
            message="Post edited and approved successfully",
            data={"post": GeneratedPostResponse.model_validate(post).model_dump(mode="json")},
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.delete("/{post_id}", response_model=SuccessMessage)
async def delete_generated_post(
    workspace_id: UUID,
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Soft-delete a generated post (sets is_deleted=True)."""
    try:
        service = GeneratedPostService(db)
        result = service.soft_delete_post(
            workspace_id,
            post_id,
            _user_id(current_user),
        )
        return SuccessMessage(
            message=WorkspaceMessages.POST_DELETED,
            data=result,
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/{post_id}/publish-now", response_model=SuccessMessage)
async def publish_post_now(
    workspace_id: UUID,
    post_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Manually enqueue Instagram publish, bypassing scheduled_for."""
    try:
        service = GeneratedPostService(db)
        result = service.enqueue_publish_now(
            workspace_id,
            post_id,
            _user_id(current_user),
        )
        background_tasks.add_task(publish_post, str(post_id))
        return SuccessMessage(
            message="Publish job queued successfully",
            data=result,
            code=http_status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
