from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminOTPRequest(BaseModel):
    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class AdminOTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., pattern=r"^\d{6}$")

    model_config = ConfigDict(extra="forbid")


class ContactEnquiryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=5000)
    company_name: str | None = Field(None, max_length=255)
    plan_interest: Literal["free", "pro", "business"] | None = None

    model_config = ConfigDict(extra="forbid")


class SupportIssueCreate(BaseModel):
    message: str = Field(..., min_length=10, max_length=5000)

    model_config = ConfigDict(extra="forbid")


class ContactEnquiryUpdate(BaseModel):
    status: Literal["new", "in_progress", "resolved", "spam"] | None = None
    admin_notes: str | None = Field(None, max_length=10000)

    model_config = ConfigDict(extra="forbid")


class SetPlanRequest(BaseModel):
    plan_key: str = Field(..., min_length=1, max_length=20)
    reason: str = Field(..., min_length=5, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class ForceSubscriptionStatusRequest(BaseModel):
    status: Literal["pending", "active", "past_due", "cancelled", "expired"]
    reason: str = Field(..., min_length=5, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class AdminReasonRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class AdminBroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    deep_link: str | None = Field(None, max_length=1000)
    data: dict | None = None
    reason: str = Field(..., min_length=5, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class AdminIdentity(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None

    model_config = ConfigDict(from_attributes=True)
