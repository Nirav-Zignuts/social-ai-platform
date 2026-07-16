from typing import Any
import json
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.integrations.meta.exceptions import MetaAPIError
from app.integrations.meta.schemas import MetaGraphErrorBody


def _safe_params_for_log(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    safe: dict[str, Any] = {}
    for key, value in params.items():
        if key == "access_token" and isinstance(value, str):
            safe[key] = f"{value[:12]}...({len(value)} chars)" if value else None
        else:
            safe[key] = value
    return safe


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
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, params=params, data=data)

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

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.graph_base_url}/{path.lstrip('/')}"
        return await self._request("POST", url, params=params, data=data)

    async def delete(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.graph_base_url}/{path.lstrip('/')}"
        return await self._request("DELETE", url, params=params)

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

    async def debug_token(self, input_token: str) -> dict[str, Any]:
        """
        Inspect a user/page token via GET /debug_token.

        Uses app access token ({app_id}|{app_secret}) as required by Meta.
        Response includes expires_at (unix), is_valid, scopes, etc.
        """
        app_access_token = f"{self.app_id}|{self.app_secret}"
        return await self.get(
            "debug_token",
            params={
                "input_token": input_token,
                "access_token": app_access_token,
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
                "fields": (
                    "id,username,name,biography,profile_picture_url,"
                    "followers_count,follows_count,media_count"
                ),
            },
        )

    async def get_media(
        self,
        media_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        params = {
            "access_token": access_token,
            "fields": (
                "id,caption,media_type,media_url,permalink,timestamp,"
                "like_count,comments_count"
            ),
        }
        body = await self.get(media_id, params=params)
        return body

    async def get_media_insights(
        self,
        media_id: str,
        access_token: str,
        *,
        metrics: str,
    ) -> dict[str, Any]:
        params = {
            "metric": metrics,
            "access_token": access_token,
        }
        path = f"{media_id}/insights"
        try:
            body = await self.get(path, params=params)      
            return body
        except MetaAPIError:
            raise

    async def create_media_container(
        self,
        ig_user_id: str,
        *,
        image_url: str,
        caption: str,
        access_token: str,
    ) -> dict[str, Any]:
        return await self.post(
            f"{ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": access_token,
            },
        )

    async def get_container_status(
        self,
        container_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        return await self.get(
            container_id,
            params={
                "fields": "status_code,status",
                "access_token": access_token,
            },
        )

    async def publish_media(
        self,
        ig_user_id: str,
        *,
        creation_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        return await self.post(
            f"{ig_user_id}/media_publish",
            params={
                "creation_id": creation_id,
                "access_token": access_token,
            },
        )

    async def delete_media(
        self,
        media_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        """Delete a published Instagram media object via Graph API."""
        return await self.delete(
            media_id,
            params={"access_token": access_token},
        )
