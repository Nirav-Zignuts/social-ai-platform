"""
User session repository for managing user sessions.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_session import UserSession
from app.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSession]):
    """Repository for UserSession model operations."""

    model = UserSession

    def __init__(self, db: Session):
        super().__init__(db)

    def create_session(
        self,
        user_id: UUID,
        auth_type: str,
        access_token: str,
        refresh_token: str,
        refresh_token_expires_at: datetime | None = None,
        fcm_token: str | None = None,
        platform: str | None = None,
        device_type: str | None = None,
        device_model: str | None = None,
        os_name: str | None = None,
        os_version: str | None = None,
        browser_name: str | None = None,
        browser_version: str | None = None,
        app_version: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_id: str | None = None,
    ) -> UserSession:
        """
        Create a new user session.

        Args:
            user_id: The user ID
            auth_type: Authentication type (LOCAL, GOOGLE, etc.)
            access_token: JWT access token
            refresh_token: JWT refresh token
            refresh_token_expires_at: Refresh token expiration time
            fcm_token: Firebase Cloud Messaging token
            platform: Platform information (web, mobile, desktop)
            device_type: Device type (phone, tablet, computer)
            device_model: Device model name
            os_name: Operating system name
            os_version: Operating system version
            browser_name: Browser name
            browser_version: Browser version
            app_version: Application version
            ip_address: Client IP address
            user_agent: User agent string
            device_id: Unique device identifier

        Returns:
            Created UserSession instance
        """
        session = UserSession(
            user_id=user_id,
            auth_type=auth_type,
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_token_expires_at,
            fcm_token=fcm_token,
            platform=platform,
            device_type=device_type,
            device_model=device_model,
            os_name=os_name,
            os_version=os_version,
            browser_name=browser_name,
            browser_version=browser_version,
            app_version=app_version,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_active_session(self, user_id: UUID) -> UserSession | None:
        """
        Get the most recent active session for a user.

        Args:
            user_id: The user ID

        Returns:
            UserSession or None
        """
        stmt = (
            select(UserSession)
            .where(
                (UserSession.user_id == user_id)
                & (UserSession.is_active == True)
                & (UserSession.is_deleted == False)
            )
            .order_by(UserSession.created_at.desc())
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_device_id(self, user_id: UUID, device_id: str) -> UserSession | None:
        """
        Get session by user ID and device ID.

        Args:
            user_id: The user ID
            device_id: The device ID

        Returns:
            UserSession or None
        """
        stmt = select(UserSession).where(
            (UserSession.user_id == user_id)
            & (UserSession.device_id == device_id)
            & (UserSession.is_active == True)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def invalidate_session(self, session_id: UUID) -> bool:
        """
        Mark a session as inactive.

        Args:
            session_id: The session ID

        Returns:
            True if successful
        """
        session = self.db.query(UserSession).filter_by(id=session_id).first()
        if session:
            session.is_active = False
            self.db.commit()
            return True
        return False

    def invalidate_user_sessions(self, user_id: UUID) -> int:
        """
        Mark all user sessions as inactive.

        Args:
            user_id: The user ID

        Returns:
            Number of sessions invalidated
        """
        stmt = (
            select(UserSession)
            .where(
                (UserSession.user_id == user_id)
                & (UserSession.is_active == True)
            )
        )
        sessions = self.db.execute(stmt).scalars().all()
        count = len(sessions)
        for session in sessions:
            session.is_active = False
        self.db.commit()
        return count

    def get_user_sessions(self, user_id: UUID) -> list[UserSession]:
        """
        Get all active sessions for a user.

        Args:
            user_id: The user ID

        Returns:
            List of UserSession instances
        """
        stmt = (
            select(UserSession)
            .where(
                (UserSession.user_id == user_id)
                & (UserSession.is_active == True)
                & (UserSession.is_deleted == False)
            )
            .order_by(UserSession.created_at.desc())
        )
        result = self.db.execute(stmt)
        return result.scalars().all()


    def get_session_by_token(self, token: str) -> UserSession | None:
        """
        Get session by access token.

        Args:
            token: The access token

        Returns:
            UserSession or None
        """
        stmt = select(UserSession).where(
            (UserSession.access_token == token)
            & (UserSession.is_active == True)
            & (UserSession.is_deleted == False)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    def delete_session(self, session: UserSession) -> None:
        print(f"Deleting session: {session.id}")
        self.db.delete(session)
        self.db.commit()

    def get_session_by_refresh_token(self, refresh_token: str) -> UserSession | None:
        """
        Get session by refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            UserSession or None
        """
        stmt = select(UserSession).where(
            (UserSession.refresh_token == refresh_token)
            & (UserSession.is_active == True)
            & (UserSession.is_deleted == False)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()