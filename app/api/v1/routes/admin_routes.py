from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.admin_schema import (
    AdminReasonRequest,
    ContactEnquiryUpdate,
    ForceSubscriptionStatusRequest,
    SetPlanRequest,
)
from app.common.messages import (
    AdminMessages,
    ErrorMessage,
    ErrorMessages,
    SuccessMessage,
)
from app.db.session import get_db
from app.middlewares.admin_auth import require_admin_auth
from app.models.admin import Admin
from app.publishing.tasks import publish_post
from app.services.admin_operations_service import AdminOperationsService
from app.services.contact_enquiry_service import ContactEnquiryService

router = APIRouter(
    tags=["Operations"],
    dependencies=[Depends(require_admin_auth)],
)


def _error(exc: Exception) -> ErrorMessage:
    if isinstance(exc, HTTPException):
        return ErrorMessage(message=exc.detail, code=exc.status_code)
    return ErrorMessage(
        message=ErrorMessages.SERVER_ERROR,
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=str(exc),
    )


@router.get("/contact-enquiries", response_model=SuccessMessage)
async def list_contact_enquiries(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(new|in_progress|resolved|spam)$",
    ),
    enquiry_type: str | None = Query(None, pattern="^(sales|support)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = ContactEnquiryService(db).list_enquiries(
            status=status_filter,
            enquiry_type=enquiry_type,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return SuccessMessage(
            message=AdminMessages.ENQUIRIES_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/contact-enquiries/{enquiry_id}", response_model=SuccessMessage)
async def get_contact_enquiry(
    enquiry_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        data = ContactEnquiryService(db).get_enquiry(enquiry_id)
        return SuccessMessage(
            message=AdminMessages.ENQUIRY_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.patch("/contact-enquiries/{enquiry_id}", response_model=SuccessMessage)
async def update_contact_enquiry(
    enquiry_id: UUID,
    payload: ContactEnquiryUpdate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_auth),
):
    try:
        data = ContactEnquiryService(db).update_enquiry(
            enquiry_id,
            payload,
            admin.id,
        )
        return SuccessMessage(
            message=AdminMessages.ENQUIRY_UPDATED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.delete("/contact-enquiries/{enquiry_id}", response_model=SuccessMessage)
async def delete_contact_enquiry(
    enquiry_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        ContactEnquiryService(db).delete_enquiry(enquiry_id)
        return SuccessMessage(
            message=AdminMessages.ENQUIRY_DELETED,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/ai-usage", response_model=SuccessMessage)
async def list_ai_usage(
    workspace_id: UUID | None = None,
    agent_purpose: str | None = Query(None, max_length=30),
    provider: str | None = Query(None, max_length=20),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).list_ai_usage(
            workspace_id=workspace_id,
            agent_purpose=agent_purpose,
            provider=provider,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return SuccessMessage(
            message=AdminMessages.AI_USAGE_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/ai-usage/summary", response_model=SuccessMessage)
async def ai_usage_summary(
    period: str = Query("7d", pattern="^(7d|30d)$"),
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).get_ai_usage_summary(period)
        return SuccessMessage(
            message=AdminMessages.AI_USAGE_SUMMARY_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/users", response_model=SuccessMessage)
async def list_users(
    search: str | None = Query(None, max_length=255),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).list_users(search, limit, offset)
        return SuccessMessage(
            message=AdminMessages.USERS_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/users/{user_id}", response_model=SuccessMessage)
async def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).get_user_detail(user_id)
        return SuccessMessage(
            message=AdminMessages.USER_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/workspaces/{workspace_id}", response_model=SuccessMessage)
async def get_workspace_detail(
    workspace_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).get_workspace_detail(workspace_id)
        return SuccessMessage(
            message=AdminMessages.WORKSPACE_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get(
    "/workspaces/{workspace_id}/generation-runs",
    response_model=SuccessMessage,
)
async def get_generation_runs(
    workspace_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).get_generation_runs(
            workspace_id,
            limit,
        )
        return SuccessMessage(
            message=AdminMessages.GENERATION_RUNS_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.post("/users/{user_id}/set-plan", response_model=SuccessMessage)
async def set_user_plan(
    user_id: UUID,
    payload: SetPlanRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_auth),
):
    try:
        data = AdminOperationsService(db).set_user_plan(
            user_id,
            payload.plan_key,
            payload.reason,
            admin.id,
        )
        return SuccessMessage(
            message=AdminMessages.PLAN_UPDATED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.post(
    "/subscriptions/{subscription_id}/force-status",
    response_model=SuccessMessage,
)
async def force_subscription_status(
    subscription_id: UUID,
    payload: ForceSubscriptionStatusRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_auth),
):
    try:
        data = AdminOperationsService(db).force_subscription_status(
            subscription_id,
            payload.status,
            payload.reason,
            admin.id,
        )
        return SuccessMessage(
            message=AdminMessages.SUBSCRIPTION_STATUS_UPDATED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.post("/workspaces/{workspace_id}/unlock", response_model=SuccessMessage)
async def unlock_workspace(
    workspace_id: UUID,
    payload: AdminReasonRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_auth),
):
    try:
        data = AdminOperationsService(db).unlock_workspace(
            workspace_id,
            payload.reason,
            admin.id,
        )
        return SuccessMessage(
            message=AdminMessages.WORKSPACE_UNLOCKED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.post("/publishing-jobs/{job_id}/retry", response_model=SuccessMessage)
async def retry_publishing_job(
    job_id: UUID,
    payload: AdminReasonRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_auth),
):
    try:
        data = AdminOperationsService(db).prepare_publish_retry(
            job_id,
            payload.reason,
            admin.id,
        )
        background_tasks.add_task(
            publish_post,
            str(data["post_id"]),
            bypass_attempt_cap=True,
        )
        return SuccessMessage(
            message=AdminMessages.PUBLISH_RETRY_QUEUED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)


@router.get("/action-logs", response_model=SuccessMessage)
async def list_admin_action_logs(
    action_type: str | None = Query(None, max_length=50),
    target_type: str | None = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = AdminOperationsService(db).list_action_logs(
            action_type,
            target_type,
            limit,
            offset,
        )
        return SuccessMessage(
            message=AdminMessages.ACTION_LOGS_RETRIEVED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return _error(exc)
