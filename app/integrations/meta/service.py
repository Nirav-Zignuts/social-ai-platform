from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.integrations.meta.client import MetaGraphClient
from app.integrations.meta.exceptions import (
    FacebookPageNotFound,
    InstagramAccountNotFound,
    MetaAPIError,
)
from app.integrations.meta.schemas import (
    ConnectedAccountData,
    MetaContainerStatusResponse,
    MetaFacebookPage,
    MetaInstagramProfile,
    MetaMediaContainerResponse,
    MetaMediaDetails,
    MetaMediaInsightsResponse,
    MetaPagesResponse,
    MetaPublishResponse,
    MetaTokenResponse,
)


class MetaService:
    """High-level Meta Graph API integration service."""

    def __init__(self, client: MetaGraphClient | None = None) -> None:
        self._client = client or MetaGraphClient()

    def generate_oauth_url(self, state: str) -> str:
        return self._client.build_oauth_authorization_url(
            state=state,
            scopes=settings.META_SCOPES,
        )

    async def exchange_code(self, code: str) -> MetaTokenResponse:
        data = await self._client.exchange_code_for_token(code)
        return MetaTokenResponse.model_validate(data)

    async def exchange_long_lived_token(self, short_lived_token: str) -> MetaTokenResponse:
        data = await self._client.exchange_long_lived_token(short_lived_token)
        return MetaTokenResponse.model_validate(data)

    async def get_pages(self, access_token: str) -> MetaPagesResponse:
        data = await self._client.get_pages(access_token)
        return MetaPagesResponse.model_validate(data)

    async def get_instagram_business_account(
        self,
        page_id: str,
        access_token: str,
    ) -> str | None:
        data = await self._client.get_instagram_business_account(page_id, access_token)
        ig_account = data.get("instagram_business_account")
        if not ig_account:
            return None
        if isinstance(ig_account, dict):
            return ig_account.get("id")
        return str(ig_account)

    async def get_instagram_profile(
        self,
        instagram_business_account_id: str,
        access_token: str,
    ) -> MetaInstagramProfile:
        data = await self._client.get_instagram_profile(
            instagram_business_account_id,
            access_token,
        )
        return MetaInstagramProfile.model_validate(data)

    async def resolve_instagram_business_connection(
        self,
        user_access_token: str,
        token_expires_in: int | None,
    ) -> ConnectedAccountData:
        pages_response = await self.get_pages(user_access_token)
        print("[meta] me/accounts page count:", len(pages_response.data))
        for page in pages_response.data:
            print(
                "[meta] page:",
                page.id,
                page.name,
                "instagram_business_account=",
                page.instagram_business_account,
            )

        if not pages_response.data:
            raise FacebookPageNotFound("No Facebook Pages found for this Meta account.")

        selected_page: MetaFacebookPage | None = None
        instagram_business_account_id: str | None = None

        for page in pages_response.data:
            ig_id = None
            if page.instagram_business_account and isinstance(page.instagram_business_account, dict):
                ig_id = page.instagram_business_account.get("id")

            if not ig_id:
                ig_id = await self.get_instagram_business_account(page.id, page.access_token)
                print("[meta] fetched instagram_business_account for page", page.id, "->", ig_id)

            if ig_id:
                selected_page = page
                instagram_business_account_id = ig_id
                break

        if not selected_page or not instagram_business_account_id:
            print("[meta] no page with linked Instagram Business account found")
            raise InstagramAccountNotFound(
                "No Instagram Business Account is linked to your Facebook Pages."
            )

        profile = await self.get_instagram_profile(
            instagram_business_account_id,
            selected_page.access_token,
        )
        print("[meta] instagram profile:", profile.id, profile.username, profile.name)

        expires_at = None
        if token_expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_expires_in)

        return ConnectedAccountData(
            provider_account_id=profile.id,
            provider_username=profile.username,
            display_name=profile.name,
            access_token=selected_page.access_token,
            refresh_token=None,
            expires_at=expires_at,
            page_id=selected_page.id,
            page_name=selected_page.name,
            instagram_business_account_id=instagram_business_account_id,
            profile_picture_url=profile.profile_picture_url,
            status="connected",
            connected_at=datetime.now(timezone.utc),
        )

    async def create_image_container(
        self,
        ig_user_id: str,
        *,
        image_url: str,
        caption: str,
        access_token: str,
    ) -> MetaMediaContainerResponse:
        data = await self._client.create_media_container(
            ig_user_id,
            image_url=image_url,
            caption=caption,
            access_token=access_token,
        )
        return MetaMediaContainerResponse.model_validate(data)

    async def get_container_status(
        self,
        container_id: str,
        access_token: str,
    ) -> MetaContainerStatusResponse:
        data = await self._client.get_container_status(container_id, access_token)
        return MetaContainerStatusResponse.model_validate(data)

    async def publish_container(
        self,
        ig_user_id: str,
        *,
        creation_id: str,
        access_token: str,
    ) -> MetaPublishResponse:
        data = await self._client.publish_media(
            ig_user_id,
            creation_id=creation_id,
            access_token=access_token,
        )
        return MetaPublishResponse.model_validate(data)

    async def get_media_details(
        self,
        media_id: str,
        access_token: str,
    ) -> MetaMediaDetails:
        data = await self._client.get_media(media_id, access_token)
        return MetaMediaDetails.model_validate(data)

    async def get_media_insights(
        self,
        media_id: str,
        access_token: str,
        *,
        metrics: str = "likes,comments,saved,shares,reach,views,total_interactions,profile_visits",
    ) -> MetaMediaInsightsResponse:
        data = await self._client.get_media_insights(
            media_id,
            access_token,
            metrics=metrics,
        )
        return MetaMediaInsightsResponse.model_validate(data)

    async def delete_media(self, media_id: str, access_token: str) -> dict:
        """Delete published IG media. Returns Graph success payload."""
        return await self._client.delete_media(media_id, access_token)
