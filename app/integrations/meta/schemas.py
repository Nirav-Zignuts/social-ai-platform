from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MetaTokenResponse(BaseModel):
    access_token: str
    token_type: str | None = None
    expires_in: int | None = None


class MetaFacebookPage(BaseModel):
    id: str
    name: str
    access_token: str
    instagram_business_account: dict[str, Any] | None = None


class MetaPagesResponse(BaseModel):
    data: list[MetaFacebookPage] = Field(default_factory=list)


class MetaInstagramBusinessAccount(BaseModel):
    id: str


class MetaInstagramProfile(BaseModel):
    id: str
    username: str | None = None
    name: str | None = None


class MetaGraphErrorBody(BaseModel):
    error: dict[str, Any] = Field(default_factory=dict)


class OAuthStatePayload(BaseModel):
    workspace_id: str
    provider: str
    user_id: str
    created_at: str


class ConnectedAccountData(BaseModel):
    provider_account_id: str
    provider_username: str | None
    display_name: str | None
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    page_id: str
    instagram_business_account_id: str
    status: str
    connected_at: datetime
