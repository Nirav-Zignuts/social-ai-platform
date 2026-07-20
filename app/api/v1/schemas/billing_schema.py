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
    razorpay_subscription_id: str | None = None
