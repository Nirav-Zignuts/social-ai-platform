"""Account-level billing routes (Razorpay subscriptions)."""

from uuid import UUID
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas.billing_schema import (
    BillingStatusResponse,
    CancelSubscriptionRequest,
    CheckoutResponse,
    SelectWorkspacesRequest,
    SubscribeRequest,
    PaymentEventsPage,
    PaymentEventItem,
)
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.get("/status", response_model=SuccessMessage)
@limiter.limit("60/minute")
async def billing_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = BillingService(db)
        data = service.get_status(_user_id(current_user))
        return SuccessMessage(
            message="Billing status retrieved successfully",
            data=BillingStatusResponse.model_validate(data).model_dump(mode="json"),
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            return ErrorMessage(message=e.detail, code=e.status_code)
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/subscribe", response_model=SuccessMessage)
@limiter.limit("10/minute")
async def subscribe(
    request: Request,
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = BillingService(db)
        data = service.create_checkout(_user_id(current_user), payload.plan_key)
        return SuccessMessage(
            message="Checkout created successfully",
            data=CheckoutResponse.model_validate(data).model_dump(mode="json"),
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            return ErrorMessage(message=e.detail, code=e.status_code)
        import traceback
        traceback.print_exc()
        return ErrorMessage(
            message=f"{ErrorMessages.SERVER_ERROR}: {str(e)}",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/cancel", response_model=SuccessMessage)
@limiter.limit("10/minute")
async def cancel_subscription(
    request: Request,
    payload: CancelSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        service = BillingService(db)
        data = service.cancel_subscription(
            _user_id(current_user),
            immediate=payload.immediate,
        )
        return SuccessMessage(
            message="Subscription cancellation requested",
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            return ErrorMessage(message=e.detail, code=e.status_code)
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/workspaces/select-active", response_model=SuccessMessage)
@limiter.limit("20/minute")
async def select_active_workspaces(
    request: Request,
    payload: SelectWorkspacesRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """
    After downgrade: FE sends the workspace IDs the user wants to keep active
    (at most plan.workspace_limit). All other owned workspaces become locked_over_limit.
    """
    try:
        service = BillingService(db)
        data = service.select_active_workspaces(
            _user_id(current_user),
            payload.workspace_ids,
        )
        return SuccessMessage(
            message="Active workspaces updated",
            data=data,
            code=status.HTTP_200_OK,
        )
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            return ErrorMessage(message=e.detail, code=e.status_code)
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.post("/webhooks/razorpay")
@limiter.limit("120/minute")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public Razorpay webhook endpoint (no JWT).
    Security: HMAC signature via X-Razorpay-Signature + RAZORPAY_WEBHOOK_SECRET.
    Always prefer HTTP 200 after acceptance so Razorpay does not storm retries.
    """
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")

    service = BillingService(db)
    try:
        result = service.verify_and_handle_webhook(
            raw_body=raw_body,
            signature=signature,
            event_id_header=event_id,
        )
        return JSONResponse(status_code=200, content={"status": "ok", **result})
    except HTTPException as exc:
        # Signature / config failures must not 200 — reject bad actors.
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail, "code": exc.status_code},
        )
    except Exception as exc:
        # Unexpected errors: log and still 200 to avoid retry storms after accept.
        import logging

        logging.getLogger(__name__).exception("Unhandled Razorpay webhook error: %s", exc)
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "note": "accepted"},
        )


@router.get("/transactions", response_model=PaymentEventsPage)
@limiter.limit("60/minute")
async def list_transactions(
    request: Request,
    event_type: List[str] | None = Query(None, description="Filter by Razorpay event type. Can be repeated."),
    processed: bool | None = Query(None, description="Filter by processed state (true/false)."),
    date_from: str | None = Query(None, description="ISO date/time start (inclusive)"),
    date_to: str | None = Query(None, description="ISO date/time end (inclusive)"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """List the authenticated user's payment events (webhook audit rows)."""
    try:
        svc = BillingService(db)

        dt_from = None
        dt_to = None
        if date_from:
            dt_from = datetime.fromisoformat(date_from)
        if date_to:
            dt_to = datetime.fromisoformat(date_to)

        data = svc.list_payment_events(
            user_id=_user_id(current_user),
            event_types=event_type,
            processed=processed,
            date_from=dt_from,
            date_to=dt_to,
            page=page,
            page_size=page_size,
        )

        return PaymentEventsPage.model_validate(data)
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            return ErrorMessage(message=e.detail, code=e.status_code)
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
