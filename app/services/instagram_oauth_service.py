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
from app.models.workspace import Workspace
from app.repositories.social_accounts import ConnectedAccountRepository, OAuthStateRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.workspace_service import ONBOARDING_STATUS_ORDER


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

    def _advance_onboarding_status(self, workspace: Workspace, new_minimum_status: str) -> None:
        current_weight = ONBOARDING_STATUS_ORDER.get(workspace.onboarding_status, 0)
        new_weight = ONBOARDING_STATUS_ORDER.get(new_minimum_status, 0)
        if new_weight > current_weight:
            workspace.onboarding_status = new_minimum_status

    def _mark_instagram_connected(self, workspace_id: UUID) -> None:
        from app.repositories.workspace import AIConfigurationRepository

        workspace = self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            return

        self._advance_onboarding_status(workspace, "instagram_connected")

        ai_config = AIConfigurationRepository(self.db).get_by_workspace_id(workspace_id)
        if ai_config is not None and workspace.preferred_post_time is not None:
            self._advance_onboarding_status(workspace, "completed")

        self.db.add(workspace)
        self.db.commit()

    def _redirect_success(self, workspace_id: UUID) -> RedirectResponse:
        url = f"{self._settings_redirect_url(workspace_id)}?instagram=connected"
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
        return RedirectResponse(url=url, status_code=302)

    async def get_connection(self, workspace_id: UUID, user_id: UUID) -> dict:
        workspace = self._get_owned_workspace(workspace_id, user_id)
        account = self.connected_account_repo.get_by_workspace_and_provider(
            workspace_id=workspace_id,
            provider=SocialProvider.INSTAGRAM.value,
        )
        connected = (
            account is not None
            and account.status == ConnectedAccountStatus.CONNECTED.value
        )
        metrics = None
        if (
            connected
            and account
            and account.access_token
            and account.instagram_business_account_id
        ):
            try:
                profile = await self.meta_service.get_instagram_profile(
                    account.instagram_business_account_id,
                    account.access_token,
                )
                metrics = {
                    "followers_count": profile.followers_count,
                    "follows_count": profile.follows_count,
                    "media_count": profile.media_count,
                    "biography": profile.biography,
                    "profile_picture_url": profile.profile_picture_url,
                    "username": profile.username,
                    "name": profile.name,
                }
                # Keep local username/display/avatar in sync when Meta returns fresher data.
                if profile.username and profile.username != account.provider_username:
                    account.provider_username = profile.username
                if profile.name and profile.name != account.display_name:
                    account.display_name = profile.name
                if (
                    profile.profile_picture_url
                    and profile.profile_picture_url != account.profile_picture_url
                ):
                    account.profile_picture_url = profile.profile_picture_url

                # Keep analytics dashboard in sync with Connected Account live metrics.
                from app.analytics.profile_sync import upsert_today_profile_snapshot

                upsert_today_profile_snapshot(
                    self.db,
                    workspace,
                    followers_count=int(profile.followers_count or 0),
                    follows_count=int(profile.follows_count or 0),
                    media_count=int(profile.media_count or 0),
                    account=account,
                    source="connection_status",
                )
                self.db.commit()
                self.db.refresh(account)
            except MetaIntegrationError as exc:
                print("[instagram_oauth] failed to fetch account metrics:", exc)

        return {
            "connected": connected,
            "account": account,
            "metrics": metrics,
        }

    async def initiate_connect(self, workspace_id: UUID, user_id: UUID) -> dict:
        self._get_owned_workspace(workspace_id, user_id)

        state = await self.oauth_state_repo.create(
            workspace_id=workspace_id,
            provider=SocialProvider.INSTAGRAM,
            user_id=user_id,
        )
        authorization_url = self.meta_service.generate_oauth_url(state)
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
            long_lived = await self.meta_service.exchange_long_lived_token(
                short_lived.access_token
            )
            account_data = await self.meta_service.resolve_instagram_business_connection(
                user_access_token=long_lived.access_token,
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
                    "expires_at": None,
                    "page_id": account_data.page_id,
                    "page_name": account_data.page_name,
                    "instagram_business_account_id": account_data.instagram_business_account_id,
                    "profile_picture_url": account_data.profile_picture_url,
                    "status": ConnectedAccountStatus.CONNECTED.value,
                    "connected_at": account_data.connected_at,
                    "last_sync_at": None,
                },
            )

            # After DB insert: inspect stored page token and persist unix expiry.
            try:
                debug_payload = await self.meta_service.debug_token(saved.access_token)
                expires_at = MetaService.expires_at_from_debug(debug_payload)
                if expires_at is not None:
                    saved.expires_at = expires_at
                    self.connected_account_repo.update(saved)
                else:
                    print(
                        "[instagram_oauth] no usable unix expiry "
                        "(expires_at=0 and data_access_expires_at missing)"
                    )
            except Exception as debug_exc:
                print(
                    "[instagram_oauth] debug_token after connect failed "
                    "(account still connected):",
                    debug_exc,
                )
        except MetaIntegrationError as exc:
            print("[instagram_oauth] MetaIntegrationError:", exc)
            return self._redirect_error(workspace_id, str(exc))
        except Exception as exc:
            print("[instagram_oauth] unexpected error:", exc)
            traceback.print_exc()
            return self._redirect_error(workspace_id, "Instagram connection failed.")

        self._mark_instagram_connected(workspace_id)
        return self._redirect_success(workspace_id)

    async def disconnect(self, workspace_id: UUID, user_id: UUID) -> dict:
        """Disconnect Instagram for a workspace (clears tokens, keeps row for reconnect)."""
        workspace = self._get_owned_workspace(workspace_id, user_id)
        account = self.connected_account_repo.get_by_workspace_and_provider(
            workspace_id=workspace_id,
            provider=SocialProvider.INSTAGRAM.value,
        )
        if not account:
            raise HTTPException(
                status_code=404,
                detail="No Instagram account connected for this workspace",
            )

        already = account.status == ConnectedAccountStatus.DISCONNECTED.value
        account.status = ConnectedAccountStatus.DISCONNECTED.value
        account.access_token = ""
        account.refresh_token = None
        account.expires_at = None
        account.is_active = False
        self.db.add(account)

        if workspace.onboarding_status in ("instagram_connected", "completed"):
            workspace.onboarding_status = "ai_configured"
            self.db.add(workspace)

        self.db.commit()
        self.db.refresh(account)

        return {
            "workspace_id": str(workspace_id),
            "provider": SocialProvider.INSTAGRAM.value,
            "status": account.status,
            "already_disconnected": already,
            "onboarding_status": workspace.onboarding_status,
        }

    def _get_owned_workspace(self, workspace_id: UUID, user_id: UUID):
        workspace = self.workspace_repo.get_owned_workspace(workspace_id, user_id)
        if not workspace:
            existing = self.workspace_repo.get_by_id(workspace_id)
            if existing and not existing.is_deleted:
                raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
            raise HTTPException(status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND)
        return workspace
