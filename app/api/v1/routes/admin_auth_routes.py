from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.admin_schema import AdminOTPRequest, AdminOTPVerifyRequest
from app.common.messages import (
    AdminErrorMessages,
    AdminMessages,
    ErrorMessage,
    ErrorMessages,
    SuccessMessage,
)
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services.admin_auth_service import (
    AdminAuthService,
    request_admin_otp_in_background,
)

router = APIRouter(prefix="/auth", tags=["Operations authentication"])


@router.post("/request-otp", response_model=SuccessMessage)
@limiter.limit("10/15minutes")
async def request_admin_otp(
    request: Request,
    payload: AdminOTPRequest,
    background_tasks: BackgroundTasks,
):
    try:
        # The response is intentionally identical for valid and unknown addresses.
        background_tasks.add_task(
            request_admin_otp_in_background,
            str(payload.email),
        )
        return SuccessMessage(
            message=AdminMessages.OTP_REQUESTED,
            code=status.HTTP_200_OK,
        )
    except Exception:
        # Keep this response generic even if scheduling fails.
        return SuccessMessage(
            message=AdminMessages.OTP_REQUESTED,
            code=status.HTTP_200_OK,
        )


@router.post("/verify-otp", response_model=SuccessMessage)
@limiter.limit("5/15minutes")
async def verify_admin_otp(
    request: Request,
    payload: AdminOTPVerifyRequest,
    db: Session = Depends(get_db),
):
    try:
        token = AdminAuthService(db).verify_otp(str(payload.email), payload.code)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=AdminErrorMessages.INVALID_OTP,
            )
        return SuccessMessage(
            message=AdminMessages.OTP_VERIFIED,
            data={
                "token": token,
                "token_type": "admin_session",
                "expires_in": settings.ADMIN_SESSION_EXPIRE_MINUTES * 60,
                "header": "X-Admin-Authorization",
            },
            code=status.HTTP_200_OK,
        )
    except HTTPException as exc:
        return ErrorMessage(message=exc.detail, code=exc.status_code)
    except Exception as exc:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(exc),
        )
