from typing import Any
import json
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.integrations.meta.exceptions import MetaAPIError
from app.integrations.meta.schemas import MetaGraphErrorBody


class MetaGraphClient:
    """Low-level async HTTP client for Meta Graph API."""

    def __init__(self) -> None:
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.redirect_uri = settings.META_REDIRECT_URI
        self.graph_version = settings.META_GRAPH_VERSION
        self.graph_base_url = f"https://graph.facebook.com/{self.graph_version}"
        self.oauth_dialog_url = f"https://www.facebook.com/{self.graph_version}/dialog/oauth"

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, params=params)

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if response.is_error or "error" in body:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            message = error.get("message", "Meta Graph API request failed")
            raise MetaAPIError(
                message=message,
                status_code=response.status_code,
                response_body=body if isinstance(body, dict) else {"raw": body},
            )

        return body if isinstance(body, dict) else {"data": body}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.graph_base_url}/{path.lstrip('/')}"
        return await self._request("GET", url, params=params)

    def build_oauth_authorization_url(self, state: str, scopes: str) -> str:
        query = urlencode(
            {
                "client_id": self.app_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
                "scope": scopes,
                "response_type": "code",
                "config_id":"2245501072654517"
            }
        )
        return f"{self.oauth_dialog_url}?{query}"

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        return await self.get(
            "oauth/access_token",
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )

    async def exchange_long_lived_token(self, short_lived_token: str) -> dict[str, Any]:
        return await self.get(
            "oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_lived_token,
            },
        )

    async def get_pages(self, access_token: str) -> dict[str, Any]:
        return await self.get(
            "me/accounts",
            params={
                "access_token": access_token,
                "fields": "id,name,access_token,instagram_business_account",
            },
        )

    async def get_instagram_business_account(
        self,
        page_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        return await self.get(
            page_id,
            params={
                "access_token": access_token,
                "fields": "instagram_business_account",
            },
        )

    async def get_instagram_profile(
        self,
        instagram_business_account_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        return await self.get(
            instagram_business_account_id,
            params={
                "access_token": access_token,
                "fields": "id,username,name",
            },
        )
