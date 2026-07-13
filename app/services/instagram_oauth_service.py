from urllib.parse import quote
from uuid import UUID
import traceback

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.common.messages import ErrorMessages
from app.core.config import settings
from app.core.enums import ConnectedAccountStatus, SocialProvider
from app.integrations.meta.exceptions import MetaIntegrationError, OAuthStateExpired, OAuthStateInvalid
from app.integrations.meta.service import MetaService
from app.repositories.social_accounts import ConnectedAccountRepository, OAuthStateRepository
from app.repositories.workspace import WorkspaceRepository


class InstagramOAuthService:
    """Business logic for Instagram OAuth connection flow."""

    def __init__(
        self,
        db: Session,
        oauth_state_repo: OAuthStateRepository,
        meta_service: MetaService | None = None,
    ) -> None:
        self.db = db
        self.oauth_state_repo = oauth_state_repo
        self.meta_service = meta_service or MetaService()
        self.workspace_repo = WorkspaceRepository(db)
        self.connected_account_repo = ConnectedAccountRepository(db)

    def _settings_redirect_url(self, workspace_id: UUID) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/workspaces/{workspace_id}/settings"

    def _fallback_redirect_url(self) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/workspaces"

    def _redirect_success(self, workspace_id: UUID) -> RedirectResponse:
        url = f"{self._settings_redirect_url(workspace_id)}?instagram=connected"
        print("[instagram_oauth] redirect success ->", url)
        return RedirectResponse(url=url, status_code=302)

    def _redirect_error(
        self,
        workspace_id: UUID | None,
        error: str,
    ) -> RedirectResponse:
        base = (
            f"{self._settings_redirect_url(workspace_id)}?instagram=error"
            if workspace_id
            else f"{self._fallback_redirect_url()}?instagram=error"
        )
        url = f"{base}&error={quote(error)}"
        print("[instagram_oauth] redirect error ->", url)
        return RedirectResponse(url=url, status_code=302)

    def get_connection(self, workspace_id: UUID, user_id: UUID) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        account = self.connected_account_repo.get_by_workspace_and_provider(
            workspace_id=workspace_id,
            provider=SocialProvider.INSTAGRAM.value,
        )
        return {
            "connected": account is not None
            and account.status == ConnectedAccountStatus.CONNECTED.value,
            "account": account,
        }

    async def initiate_connect(self, workspace_id: UUID, user_id: UUID) -> dict:
        self._get_owned_workspace(workspace_id, user_id)

        state = await self.oauth_state_repo.create(
            workspace_id=workspace_id,
            provider=SocialProvider.INSTAGRAM,
            user_id=user_id,
        )
        authorization_url = self.meta_service.generate_oauth_url(state)
        print("[instagram_oauth] authorization_url ->", authorization_url)
        return {"authorization_url": authorization_url}

    async def handle_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        error: str | None = None,
    ) -> RedirectResponse:
        workspace_id: UUID | None = None

        if error:
            return self._redirect_error(workspace_id, error)

        if not code or not state:
            return self._redirect_error(
                workspace_id,
                "Missing authorization code or state.",
            )

        try:
            state_payload = await self.oauth_state_repo.consume(
                state=state,
                provider=SocialProvider.INSTAGRAM,
            )
            workspace_id = UUID(state_payload.workspace_id)
        except (OAuthStateExpired, OAuthStateInvalid) as exc:
            return self._redirect_error(workspace_id, str(exc))

        if not self.workspace_repo.get_by_id(workspace_id):
            return self._redirect_error(workspace_id, ErrorMessages.WORKSPACE_NOT_FOUND)

        try:
            short_lived = await self.meta_service.exchange_code(code)
            print("[instagram_oauth] short-lived token ->", short_lived)
            print("[instagram_oauth] short-lived token exchanged")
            long_lived = await self.meta_service.exchange_long_lived_token(
                short_lived.access_token
            )
            print("[instagram_oauth] long-lived token exchanged, expires_in=", long_lived.expires_in)
            print("[instagram_oauth] long-lived token ->", long_lived)
            print("[instagram_oauth] long-lived token ->", long_lived.access_token)
            account_data = await self.meta_service.resolve_instagram_business_connection(
                user_access_token=long_lived.access_token,
                token_expires_in=long_lived.expires_in,
            )
            print(
                "[instagram_oauth] resolved IG account:",
                account_data.provider_username,
                account_data.provider_account_id,
            )
            saved = self.connected_account_repo.save_connected_account(
                workspace_id=workspace_id,
                provider=SocialProvider.INSTAGRAM.value,
                account_data={
                    "provider_account_id": account_data.provider_account_id,
                    "provider_username": account_data.provider_username,
                    "display_name": account_data.display_name,
                    "access_token": account_data.access_token,
                    "refresh_token": account_data.refresh_token,
                    "expires_at": account_data.expires_at,
                    "page_id": account_data.page_id,
                    "instagram_business_account_id": account_data.instagram_business_account_id,
                    "status": ConnectedAccountStatus.CONNECTED.value,
                    "connected_at": account_data.connected_at,
                    "last_sync_at": None,
                },
            )
            print("[instagram_oauth] saved connected_account id=", saved.id, "workspace_id=", workspace_id)
        except MetaIntegrationError as exc:
            print("[instagram_oauth] MetaIntegrationError:", exc)
            return self._redirect_error(workspace_id, str(exc))
        except Exception as exc:
            print("[instagram_oauth] unexpected error:", exc)
            traceback.print_exc()
            return self._redirect_error(workspace_id, "Instagram connection failed.")

        print("[instagram_oauth] success redirect workspace_id=", workspace_id)
        return self._redirect_success(workspace_id)

    def _get_owned_workspace(self, workspace_id: UUID, user_id: UUID):
        workspace = self.workspace_repo.get_owned_workspace(workspace_id, user_id)
        if not workspace:
            if self.workspace_repo.get_by_id(workspace_id):
                raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        return workspace
