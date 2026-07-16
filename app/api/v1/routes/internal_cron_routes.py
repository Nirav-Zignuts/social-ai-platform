"""Internal cron endpoints for scheduled generation and publishing."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.analytics.insight_sync import poll_insight_sync, sync_insights_for_recent_posts
from app.analytics.profile_sync import poll_profile_sync, sync_profile_metrics_for_workspace
from app.core.rate_limit import limiter
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
@limiter.exempt
async def generate_content(request: Request, background_tasks: BackgroundTasks):
    """
    Cron: every 15 minutes.
    Stamp due workspaces and queue generation cycles as background jobs.
    """
    try:
        result = poll_generation_due()

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
@limiter.exempt
async def publish_content(request: Request, background_tasks: BackgroundTasks):
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


@router.post(
    "/poll-profile-sync",
    response_model=SuccessMessage,
    dependencies=[Depends(require_cron_secret)],
)
@limiter.exempt
async def poll_profile_sync_route(request: Request, background_tasks: BackgroundTasks):
    """
    Cron: once per day (workspace-local).
    Snapshot Instagram profile metrics for connected workspaces.
    """
    try:
        result = poll_profile_sync()
        for workspace_id in result["workspace_ids"]:
            background_tasks.add_task(sync_profile_metrics_for_workspace, workspace_id)

        return SuccessMessage(
            message="Profile sync poll completed",
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
    "/poll-insight-sync",
    response_model=SuccessMessage,
    dependencies=[Depends(require_cron_secret)],
)
@limiter.exempt
async def poll_insight_sync_route(request: Request, background_tasks: BackgroundTasks):
    """
    Cron: every 4–6 hours.
    Refresh insights for posts published in the last 14 days and append snapshots.
    """
    try:
        result = poll_insight_sync()
        background_tasks.add_task(sync_insights_for_recent_posts)

        return SuccessMessage(
            message="Insight sync poll completed",
            data=result,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
