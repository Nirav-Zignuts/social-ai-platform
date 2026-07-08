"""
User authentication provider repository.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuthProvider
from app.models.user_auth_provider import UserAuthProvider
from app.repositories.base import BaseRepository


class UserAuthProviderRepository(BaseRepository[UserAuthProvider]):
    """Repository for UserAuthProvider model operations."""

    model = UserAuthProvider

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_user_id_and_provider(
        self, user_id: UUID, provider: AuthProvider
    ) -> UserAuthProvider | None:
        """
        Get auth provider by user ID and provider type.

        Args:
            user_id: The user ID
            provider: The auth provider (LOCAL, GOOGLE, etc.)

        Returns:
            UserAuthProvider or None
        """
        stmt = select(UserAuthProvider).where(
            (UserAuthProvider.user_id == user_id)
            & (UserAuthProvider.provider == provider)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def create_auth_provider(
        self,
        user_id: UUID,
        provider: AuthProvider,
        password_hash: str | None = None,
        provider_user_id: str | None = None,
        commit: bool = True,
    ) -> UserAuthProvider:
        """
        Create a new authentication provider record.

        Args:
            user_id: The user ID
            provider: The auth provider type
            password_hash: Hashed password (for LOCAL provider)
            provider_user_id: Provider-specific user ID (for OAuth)

        Returns:
            Created UserAuthProvider instance
        """
        auth_provider = UserAuthProvider(
            user_id=user_id,
            provider=provider,
            password_hash=password_hash,
            provider_user_id=provider_user_id,
        )
        self.db.add(auth_provider)
        if commit:
            self.db.commit()
            self.db.refresh(auth_provider)
        else:
            self.db.flush()
        return auth_provider
