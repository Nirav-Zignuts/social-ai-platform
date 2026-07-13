from pydantic import BaseModel


class GoogleOAuthStatePayload(BaseModel):
    provider: str = "google"
    redirect_url: str
    fcm_token: str | None = None
    created_at: str


class GoogleTokenResponse(BaseModel):
    access_token: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    token_type: str | None = None
    id_token: str | None = None


class GoogleUserInfo(BaseModel):
    sub: str
    email: str
    email_verified: bool | None = None
    name: str | None = None
    picture: str | None = None
