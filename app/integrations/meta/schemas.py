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
    biography: str | None = None
    profile_picture_url: str | None = None
    followers_count: int | None = None
    follows_count: int | None = None
    media_count: int | None = None


class MetaMediaDetails(BaseModel):
    id: str
    caption: str | None = None
    media_type: str | None = None
    media_url: str | None = None
    permalink: str | None = None
    timestamp: str | None = None
    like_count: int | None = None
    comments_count: int | None = None


class MetaInsightMetric(BaseModel):
    name: str
    period: str | None = None
    title: str | None = None
    description: str | None = None
    values: list[dict[str, Any]] = Field(default_factory=list)
    total_value: dict[str, Any] | None = None

    def extract_value(self) -> int | None:
        raw = None
        if self.total_value and isinstance(self.total_value, dict):
            raw = self.total_value.get("value")
        if raw is None and self.values:
            raw = self.values[0].get("value")
        if raw is None:
            return None
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
        if isinstance(raw, str):
            try:
                return int(float(raw))
            except ValueError:
                return None
        return None


class MetaMediaInsightsResponse(BaseModel):
    data: list[MetaInsightMetric] = Field(default_factory=list)

    def as_map(self) -> dict[str, int | None]:
        return {metric.name: metric.extract_value() for metric in self.data}


class MetaMediaContainerResponse(BaseModel):
    id: str


class MetaContainerStatusResponse(BaseModel):
    status_code: str | None = None
    status: str | None = None


class MetaPublishResponse(BaseModel):
    id: str


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
    page_name: str | None = None
    instagram_business_account_id: str
    profile_picture_url: str | None = None
    status: str
    connected_at: datetime
