from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.admin_schema import SupportIssueCreate
from app.common.messages import (
    ContactMessages,
    ErrorMessage,
    ErrorMessages,
    SuccessMessage,
)
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.services.contact_enquiry_service import ContactEnquiryService

router = APIRouter(prefix="/support", tags=["Support"])


@router.post("/issues", response_model=SuccessMessage)
@limiter.limit("5/hour")
async def report_issue(
    request: Request,
    payload: SupportIssueCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        raw_user_id = current_user["user_id"]
        user_id = UUID(raw_user_id) if isinstance(raw_user_id, str) else raw_user_id
        ContactEnquiryService(db).submit_support_issue(
            user_id,
            payload.message,
        )
        return SuccessMessage(
            message=ContactMessages.SUPPORT_ISSUE_SUBMITTED,
            code=status.HTTP_201_CREATED,
        )
    except HTTPException as exc:
        return ErrorMessage(message=exc.detail, code=exc.status_code)
    except Exception as exc:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(exc),
        )
