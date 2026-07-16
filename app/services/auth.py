"""
Authentication service business logic.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models import user_session
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1.schemas.auth_schema import (
    DeviceDetailsPayload,
    LoginRequest,
    RegisterRequest,
)
from app.common.messages import AuthMessages, ErrorMessages
from app.core.config import settings
from app.core.constants import (
    TOKEN_SUBJECT_ACCESS,
    TOKEN_SUBJECT_ACTIVATION,
    TOKEN_SUBJECT_REFRESH,
)
from app.core.enums import AuthProvider, UserStatus
from app.repositories.auth import UserAuthProviderRepository
from app.repositories.user import UserRepository
from app.repositories.user_session import UserSessionRepository
from app.security.hashing import hash_password, verify_password
from app.security.token import (
    InvalidTokenError,
    TokenExpiredError,
    token_manager,
)
from app.common.responses import SuccessResponse
from app.middlewares.auth_middleware import get_token_from_header


class AuthenticationError(Exception):
    """Base exception for authentication errors."""

    pass


class UserAlreadyExistsError(AuthenticationError):
    """User already exists error."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials error."""

    pass


class AuthService:
    """
    Service for handling authentication operations.
    Manages business logic for registration, login, and token generation.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.auth_provider_repo = UserAuthProviderRepository(db)
        self.session_repo = UserSessionRepository(db)

    def register_user(
        self,
        request: RegisterRequest,
        device_details: DeviceDetailsPayload | None = None,
    ) -> dict:
        """
        Register a new user with email and password.

        Args:
            request: RegisterRequest containing email, password, full_name
            device_details: Optional device details for session

        Returns:
            Dictionary with user data and tokens

        Raises:
            UserAlreadyExistsError: If user with email already exists
        """
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(request.email)
        if existing_user:
            raise UserAlreadyExistsError(ErrorMessages.EMAIL_ALREADY_EXISTS)

        # Use manual commit/rollback so partial writes do not persist
        try:
            # Create new user in pending state until email verification
            user = self.user_repo.create_user(
                email=request.email,
                full_name=request.full_name,
                is_active=False,
                commit=False,
            )

            # Hash password and create auth provider (defer commit)
            password_hash = hash_password(request.password)
            self.auth_provider_repo.create_auth_provider(
                user_id=user.id,
                provider=AuthProvider.LOCAL,
                password_hash=password_hash,
                commit=False,
            )

            

            # Generate email activation token after user creation
            activation_token = token_manager.create_activation_token(
                subject=str(user.id)
            )
            # Persist both records together
            self.db.commit()
            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "status": user.status,
                    "avatar_url": user.avatar_url,
                },
                "activation_token": activation_token,
            }
        except Exception:
            self.db.rollback()
            raise

    def login_user(self, request: LoginRequest) -> dict:
        """
        Authenticate user with email and password.

        Args:
            request: LoginRequest containing email, password, and optional device_details

        Returns:
            Dictionary with user data and tokens

        Raises:
            InvalidCredentialsError: If email not found or password incorrect
        """
        # Get user by email
        user = self.user_repo.get_by_email(request.email)
        if not user:
            raise InvalidCredentialsError(ErrorMessages.INVALID_CREDENTIALS)

        # Get auth provider for LOCAL authentication
        auth_provider = self.auth_provider_repo.get_by_user_id_and_provider(
            user_id=user.id,
            provider=AuthProvider.LOCAL,
        )

        if not auth_provider or not auth_provider.password_hash:
            raise InvalidCredentialsError(ErrorMessages.INVALID_CREDENTIALS)

        # Verify password
        if not verify_password(request.password, auth_provider.password_hash):
            raise InvalidCredentialsError(ErrorMessages.INVALID_CREDENTIALS)

        # Ensure email verification is complete before allowing login
        if not user.is_active or user.status != UserStatus.ACTIVE:
            raise AuthenticationError(ErrorMessages.EMAIL_NOT_VERIFIED)

        # Generate tokens
        access_token = token_manager.create_access_token(subject=str(user.id))
        refresh_token = token_manager.create_refresh_token(subject=str(user.id))

        # Create session with device details and FCM token
        self._create_user_session(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            fcm_token=request.fcm_token,
            device_details=request.device_details,
        )

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "avatar_url": user.avatar_url,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def create_oauth_session(
        self,
        user_id: UUID,
        *,
        auth_provider: AuthProvider,
        fcm_token: str | None = None,
    ) -> dict:
        access_token = token_manager.create_access_token(subject=str(user_id))
        refresh_token = token_manager.create_refresh_token(subject=str(user_id))
        self._create_user_session(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            fcm_token=fcm_token,
            device_details=None,
            auth_type=auth_provider,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def _create_user_session(
        self,
        user_id: UUID,
        access_token: str,
        refresh_token: str,
        fcm_token: str | None = None,
        device_details: DeviceDetailsPayload | None = None,
        auth_type: AuthProvider = AuthProvider.LOCAL,
    ) -> None:
        """
        Create a user session record.

        Args:
            user_id: The user ID
            access_token: The access token
            refresh_token: The refresh token
            fcm_token: Optional FCM token
            device_details: Optional device details
        """
        refresh_token_expires_at = (
            datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )

        device_data = device_details.model_dump(exclude_none=False) if device_details else {}

        self.session_repo.create_session(
            user_id=user_id,
            auth_type=auth_type.value,
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_token_expires_at,
            fcm_token=fcm_token,
            platform=device_data.get("platform"),
            device_type=device_data.get("device_type"),
            device_model=device_data.get("device_model"),
            os_name=device_data.get("os_name"),
            os_version=device_data.get("os_version"),
            browser_name=device_data.get("browser_name"),
            browser_version=device_data.get("browser_version"),
            app_version=device_data.get("app_version"),
            ip_address=device_data.get("ip_address"),
            user_agent=device_data.get("user_agent"),
            device_id=device_data.get("device_id"),
        )

    def verify_email(self, token: str) -> None:
        """
        Verify user email using activation token.

        Args:
            token: Activation JWT token

        Raises:
            InvalidTokenError: If token is invalid or type mismatched
            TokenExpiredError: If token is expired
        """
        token_manager.validate_token_type(token, TOKEN_SUBJECT_ACTIVATION)
        user_id = token_manager.get_subject_from_token(token)

        user = self.db.get(self.user_repo.model, UUID(user_id))
        if not user:
            raise InvalidTokenError(ErrorMessages.INVALID_TOKEN)

        if user.is_active and user.status == UserStatus.ACTIVE:
            raise InvalidTokenError(ErrorMessages.EMAIL_ALREADY_VERIFIED)

        user.status = UserStatus.ACTIVE
        user.is_active = True
        user.email_verified_at = datetime.now(timezone.utc)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

    def validate_access_token(self, token: str) -> str:
        """
        Validate access token and return user ID.

        Args:
            token: JWT access token

        Returns:
            User ID from token

        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
        """
        token_manager.validate_token_type(token, TOKEN_SUBJECT_ACCESS)
        return token_manager.get_subject_from_token(token)

    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Generate new access token using refresh token.

        Args:
            refresh_token: JWT refresh token

        Returns:
            Dictionary with new access token

        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
        """
        token_manager.validate_token_type(refresh_token, TOKEN_SUBJECT_REFRESH)
        user_id = token_manager.get_subject_from_token(refresh_token)

        # Create new access token
        access_token = token_manager.create_access_token(subject=user_id)
        session = self.session_repo.get_session_by_refresh_token(refresh_token)
        if not session:
            raise InvalidTokenError(ErrorMessages.INVALID_TOKEN)
        session.access_token = access_token
        self.db.commit()
        self.db.refresh(session)

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }
    
    def get_user_by_id(self, user_id: UUID) -> dict | None:
        """
        Retrieve user details by user ID.

        Args:
            user_id: The user ID

        Returns:
            Dictionary with user data or None if not found
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        user_data = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at,
        }
        
        return SuccessResponse(
            message=AuthMessages.USER_RETRIEVED,
            data=user_data,
        )


    def logout_user(self,request: Request, user_id: UUID, device_id: str | None = None) -> None:
        """
        Logout user by invalidating their session.

        Args:
            user_id: The user ID
            device_id: Optional device ID to target specific session

        Raises:
            Exception: If session not found or deletion fails
        """
        token = get_token_from_header(request)
        session = self.session_repo.get_session_by_token(token)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found for the given user and device.")

        self.session_repo.delete_session(session)