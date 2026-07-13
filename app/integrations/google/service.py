from app.integrations.google.client import GoogleOAuthClient
from app.integrations.google.schemas import GoogleTokenResponse, GoogleUserInfo


class GoogleOAuthIntegrationService:
    """High-level Google OAuth API wrapper."""

    def __init__(self, client: GoogleOAuthClient | None = None) -> None:
        self._client = client or GoogleOAuthClient()

    def generate_oauth_url(self, state: str) -> str:
        return self._client.build_authorization_url(state)

    async def exchange_code(self, code: str) -> GoogleTokenResponse:
        data = await self._client.exchange_code(code)
        return GoogleTokenResponse.model_validate(data)

    async def get_userinfo(self, access_token: str) -> GoogleUserInfo:
        data = await self._client.get_userinfo(access_token)
        return GoogleUserInfo.model_validate(data)
