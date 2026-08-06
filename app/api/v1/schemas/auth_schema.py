from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.enums import UserStatus


class DeviceDetailsPayload(BaseModel):
    """Device and platform information payload."""

    platform: Optional[str] = Field(None, max_length=100)
    device_type: Optional[str] = Field(None, max_length=100)
    device_model: Optional[str] = Field(None, max_length=255)
    os_name: Optional[str] = Field(None, max_length=100)
    os_version: Optional[str] = Field(None, max_length=100)
    browser_name: Optional[str] = Field(None, max_length=100)
    browser_version: Optional[str] = Field(None, max_length=100)
    app_version: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None, max_length=100)
    user_agent: Optional[str] = Field(None, max_length=512)
    device_id: Optional[str] = Field(None, max_length=255)

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    fcm_token: Optional[str] = None
    device_details: Optional[DeviceDetailsPayload] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class UpdateFcmTokenRequest(BaseModel):
    """Register or clear the FCM token for the current session."""

    fcm_token: Optional[str] = Field(
        default=None,
        max_length=512,
        description="FCM device token. Pass null/omit to clear.",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class VerifyEmailRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    status: UserStatus
    avatar_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"