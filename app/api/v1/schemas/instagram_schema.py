from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
    instagram_business_account_id: str | None
    status: str
    connected_at: datetime
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstagramCallbackResponse(BaseModel):
    connected_account: ConnectedAccountResponse
    message: str = "Instagram Business Account connected successfully."


class InstagramConnectionStatusResponse(BaseModel):
    connected: bool
    account: ConnectedAccountResponse | None = None
