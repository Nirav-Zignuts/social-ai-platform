from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.admin_schema import ContactEnquiryCreate
from app.common.messages import (
    ContactMessages,
    ErrorMessage,
    ErrorMessages,
    SuccessMessage,
)
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services.contact_enquiry_service import ContactEnquiryService

router = APIRouter(prefix="/public", tags=["Public contact"])


@router.post("/contact-enquiries", response_model=SuccessMessage)
@limiter.limit("5/hour")
async def submit_contact_enquiry(
    request: Request,
    payload: ContactEnquiryCreate,
    db: Session = Depends(get_db),
):
    try:
        ContactEnquiryService(db).submit_sales_enquiry(payload)
        return SuccessMessage(
            message=ContactMessages.ENQUIRY_SUBMITTED,
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
