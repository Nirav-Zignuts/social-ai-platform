from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    model = User

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_email(self, email: str) -> User | None:
        """
        Get user by email address.

        Args:
            email: User email address

        Returns:
            User or None
        """
        stmt = select(User).where(User.email == email.lower())
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def create_user(
        self,
        email: str,
        full_name: str,
        avatar_url: str | None = None,
        is_active: bool = False,
        status: UserStatus = UserStatus.PENDING,
        email_verified_at: datetime | None = None,
        commit: bool = True,
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email address
            full_name: User full name
            avatar_url: Optional user avatar URL
            is_active: Whether the user is active

        Returns:
            Created User instance
        """
        user = User(
            email=email.lower(),
            full_name=full_name,
            avatar_url=avatar_url,
            status=status,
            is_active=is_active,
            email_verified_at=email_verified_at,
        )
        self.db.add(user)
        if commit:
            self.db.commit()
            self.db.refresh(user)
        else:
            # ensure the object has generated PKs etc.
            self.db.flush()
        return user