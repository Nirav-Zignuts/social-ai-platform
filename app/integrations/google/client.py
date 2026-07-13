from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.integrations.google.exceptions import GoogleAPIError


class GoogleOAuthClient:
    """Low-level async HTTP client for Google OAuth endpoints."""

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self) -> None:
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        self.scopes = settings.GOOGLE_OAUTH_SCOPES

    async def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                data=data,
                params=params,
                headers=headers,
            )

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if response.is_error:
            message = body.get("error_description") or body.get("error") or "Google API request failed"
            raise GoogleAPIError(str(message), status_code=response.status_code)

        return body if isinstance(body, dict) else {"data": body}

    def build_authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": self.scopes,
                "state": state,
                "access_type": "online",
                "include_granted_scopes": "true",
                "prompt": "select_account",
            }
        )
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            self.TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            self.USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
