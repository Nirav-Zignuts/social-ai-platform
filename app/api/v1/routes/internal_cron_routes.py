"""Internal cron endpoints for scheduled generation and publishing."""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.generation.tasks import poll_generation_due
from app.middlewares.auth_middleware import require_cron_secret
from app.publishing.tasks import poll_due_posts, publish_post
from app.services.generation_tasks import run_generation_cycle

router = APIRouter(prefix="/internal", tags=["Internal Cron"])


@router.post(
    "/generate-content",
    response_model=SuccessMessage,
    dependencies=[Depends(require_cron_secret)],
)
async def generate_content(background_tasks: BackgroundTasks):
    """
    Cron: every 15 minutes.
    Stamp due workspaces and queue generation cycles as background jobs.
    """
    try:
        result = poll_generation_due()
        print(f"Generation poll completed: {result}")
        for workspace_id in result["workspace_ids"]:
            background_tasks.add_task(run_generation_cycle, workspace_id)

        return SuccessMessage(
            message="Generation poll completed",
            data=result,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post(
    "/publish-content",
    response_model=SuccessMessage,
    dependencies=[Depends(require_cron_secret)],
)
async def publish_content(background_tasks: BackgroundTasks):
    """
    Cron: every 2 minutes.
    Find due approved posts and queue Instagram publishes as background jobs.
    """
    try:
        result = poll_due_posts()
        for post_id in result["post_ids"]:
            background_tasks.add_task(publish_post, post_id)

        return SuccessMessage(
            message="Publish poll completed",
            data=result,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
