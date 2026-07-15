from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class InstagramConnectResponse(BaseModel):
    authorization_url: str


class ConnectedAccountResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    provider: str
    provider_account_id: str
    provider_username: str | None
    display_name: str | None
    page_id: str | None
    page_name: str | None = None
    instagram_business_account_id: str | None
    profile_picture_url: str | None = None
    status: str
    connected_at: datetime
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def token_expired(self) -> bool:
        if self.expires_at is None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expires_in_seconds(self) -> int | None:
        """Seconds until token expiry (None if unknown / non-expiring). Negative if expired."""
        if self.expires_at is None:
            return None
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return int((expires - datetime.now(timezone.utc)).total_seconds())


class InstagramAccountMetrics(BaseModel):
    followers_count: int | None = None
    follows_count: int | None = None
    media_count: int | None = None
    biography: str | None = None
    profile_picture_url: str | None = None
    username: str | None = None
    name: str | None = None


class InstagramCallbackResponse(BaseModel):
    connected_account: ConnectedAccountResponse
    message: str = "Instagram Business Account connected successfully."


class InstagramConnectionStatusResponse(BaseModel):
    connected: bool
    account: ConnectedAccountResponse | None = None
    metrics: InstagramAccountMetrics | None = None
