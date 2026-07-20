from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubscribeRequest(BaseModel):
    plan_key: str = Field(..., min_length=1, max_length=20)

    model_config = ConfigDict(extra="forbid")


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = False

    model_config = ConfigDict(extra="forbid")


class CheckoutResponse(BaseModel):
    """Payload the frontend Razorpay checkout widget will need."""

    subscription_id: str
    key_id: str
    plan_key: str
    plan_name: str
    prefill: dict


class BillingPlanSummary(BaseModel):
    plan_key: str
    name: str
    price_inr: int | None = None
    workspace_limit: int | None = None


class BillingStatusResponse(BaseModel):
    plan: BillingPlanSummary
    status: str
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    workspace_count: int
    workspace_limit: int | None = None
    active_workspace_count: int = 0
    locked_workspace_count: int = 0
    needs_workspace_selection: bool = False
    razorpay_subscription_id: str | None = None


class SelectWorkspacesRequest(BaseModel):
    """Workspace IDs the user wants to keep active under the current plan limit."""

    workspace_ids: list[UUID] = Field(..., min_length=1, max_length=50)

    model_config = ConfigDict(extra="forbid")


class PaymentEventItem(BaseModel):
    id: str
    user_id: str | None = None
    razorpay_event_id: str | None = None
    event_type: str
    # User-friendly summary fields
    name: str | None = None
    status: str | None = None
    entity: dict | None = None
    payment_method: dict | None = None
    amount: int | None = None
    currency: str | None = None
    processed_at: str | None = None
    created_at: str | None = None
    # Optional full payload for debugging (omit by default)
    raw_payload: dict | None = None


class PaymentEventsPage(BaseModel):
    items: list[PaymentEventItem]
    total_items: int
    current_page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(extra="forbid")
