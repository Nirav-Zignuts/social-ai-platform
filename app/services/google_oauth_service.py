from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import AuthProvider, UserStatus
from app.integrations.google.exceptions import (
    GoogleIntegrationError,
    GoogleOAuthStateExpired,
    GoogleOAuthStateInvalid,
    GoogleRedirectNotAllowed,
)
from app.integrations.google.service import GoogleOAuthIntegrationService
from app.repositories.auth import UserAuthProviderRepository
from app.repositories.google_oauth_state import GoogleOAuthStateRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService


class GoogleOAuthService:
    """Business logic for Google OAuth login flow."""

    def __init__(
        self,
        db: Session,
        oauth_state_repo: GoogleOAuthStateRepository,
        google_service: GoogleOAuthIntegrationService | None = None,
    ) -> None:
        self.db = db
        self.oauth_state_repo = oauth_state_repo
        self.google_service = google_service or GoogleOAuthIntegrationService()
        self.user_repo = UserRepository(db)
        self.auth_provider_repo = UserAuthProviderRepository(db)
        self.auth_service = AuthService(db)

    def _allowed_redirect_urls(self) -> set[str]:
        configured = [
            url.strip()
            for url in settings.GOOGLE_OAUTH_ALLOWED_REDIRECT_URLS.split(",")
            if url.strip()
        ]
        defaults = [
            settings.FRONTEND_URL.rstrip("/"),
            f"{settings.FRONTEND_URL.rstrip('/')}/login",
            f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback",
            f"{settings.FRONTEND_URL.rstrip('/')}/auth/google/callback",
        ]
        return {url.rstrip("/") for url in configured + defaults}

    def _is_allowed_redirect_url(self, target: str) -> bool:
        normalized = target.rstrip("/")
        if normalized in self._allowed_redirect_urls():
            return True

        parsed = urlparse(normalized)
        frontend = urlparse(settings.FRONTEND_URL.rstrip("/"))
        if parsed.scheme != frontend.scheme or parsed.netloc != frontend.netloc:
            return False

        path = parsed.path.rstrip("/") or "/"
        return path == "/login"

    def _resolve_redirect_url(self, redirect_url: str | None) -> str:
        target = (redirect_url or settings.GOOGLE_OAUTH_DEFAULT_REDIRECT_URL).rstrip("/")
        if not self._is_allowed_redirect_url(target):
            raise GoogleRedirectNotAllowed("Redirect URL is not allowed.")
        return target

    def _redirect_with_error(self, redirect_url: str, error: str) -> RedirectResponse:
        separator = "&" if "?" in redirect_url else "?"
        return RedirectResponse(
            url=f"{redirect_url}{separator}error={quote(error)}",
            status_code=302,
        )

    def _redirect_with_tokens(
        self,
        redirect_url: str,
        *,
        access_token: str,
        refresh_token: str,
        token_type: str = "bearer",
    ) -> RedirectResponse:
        separator = "&" if "?" in redirect_url else "?"
        url = (
            f"{redirect_url}{separator}"
            f"access_token={quote(access_token)}"
            f"&refresh_token={quote(refresh_token)}"
            f"&token_type={quote(token_type)}"
        )
        return RedirectResponse(url=url, status_code=302)

    async def initiate_login(
        self,
        *,
        request: Request,
        redirect_url: str | None = None,
        fcm_token: str | None = None,
    ) -> RedirectResponse:
        target_redirect = self._resolve_redirect_url(redirect_url)
        state = await self.oauth_state_repo.create(
            redirect_url=target_redirect,
            fcm_token=fcm_token,
        )
        authorization_url = self.google_service.generate_oauth_url(state)
        return RedirectResponse(url=authorization_url, status_code=302)

    def _find_or_create_user(self, *, sub: str, email: str, name: str | None, picture: str | None):
        google_provider = self.auth_provider_repo.get_by_provider_user_id(
            provider=AuthProvider.GOOGLE,
            provider_user_id=sub,
        )
        if google_provider:
            user = self.user_repo.get_by_id(google_provider.user_id)
            if user and picture and not user.avatar_url:
                user.avatar_url = picture
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
            return user

        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            self.auth_provider_repo.create_auth_provider(
                user_id=existing_user.id,
                provider=AuthProvider.GOOGLE,
                provider_user_id=sub,
            )
            if existing_user.status != UserStatus.ACTIVE:
                existing_user.status = UserStatus.ACTIVE
                existing_user.is_active = True
                existing_user.email_verified_at = datetime.now(timezone.utc)
            if picture and not existing_user.avatar_url:
                existing_user.avatar_url = picture
            self.db.add(existing_user)
            self.db.commit()
            self.db.refresh(existing_user)
            return existing_user

        try:
            user = self.user_repo.create_user(
                email=email,
                full_name=name or email.split("@")[0],
                avatar_url=picture,
                is_active=True,
                status=UserStatus.ACTIVE,
                email_verified_at=datetime.now(timezone.utc),
                commit=False,
            )
            self.auth_provider_repo.create_auth_provider(
                user_id=user.id,
                provider=AuthProvider.GOOGLE,
                provider_user_id=sub,
                commit=False,
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception:
            self.db.rollback()
            raise

    async def handle_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        error: str | None,
        request: Request,
    ) -> RedirectResponse:
        fallback_redirect = settings.GOOGLE_OAUTH_DEFAULT_REDIRECT_URL.rstrip("/")

        if error:
            return self._redirect_with_error(fallback_redirect, error)

        if not code or not state:
            return self._redirect_with_error(
                fallback_redirect,
                "Missing authorization code or state.",
            )

        try:
            state_payload = await self.oauth_state_repo.consume(state)
        except (GoogleOAuthStateExpired, GoogleOAuthStateInvalid) as exc:
            return self._redirect_with_error(fallback_redirect, str(exc))

        redirect_url = state_payload.redirect_url

        try:
            token_response = await self.google_service.exchange_code(code)
            userinfo = await self.google_service.get_userinfo(token_response.access_token)

            if not userinfo.email:
                return self._redirect_with_error(redirect_url, "Google account has no email.")

            user = self._find_or_create_user(
                sub=userinfo.sub,
                email=userinfo.email,
                name=userinfo.name,
                picture=userinfo.picture,
            )
            if not user:
                return self._redirect_with_error(redirect_url, "Unable to create or load user.")

            tokens = self.auth_service.create_oauth_session(
                user_id=UUID(str(user.id)),
                auth_provider=AuthProvider.GOOGLE,
                fcm_token=state_payload.fcm_token,
            )
        except GoogleIntegrationError as exc:
            return self._redirect_with_error(redirect_url, str(exc))
        except Exception:
            return self._redirect_with_error(redirect_url, "Google sign-in failed.")

        return self._redirect_with_tokens(
            redirect_url,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens.get("token_type", "bearer"),
        )
