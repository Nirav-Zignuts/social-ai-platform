from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken
from app.repositories.base import BaseRepository


class DeviceTokenRepository(BaseRepository[DeviceToken]):
    model = DeviceToken

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_token(self, token: str) -> DeviceToken | None:
        stmt = select(DeviceToken).where(
            DeviceToken.token == token,
            DeviceToken.is_deleted.is_(False),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active_tokens_for_user(self, user_id: UUID) -> list[DeviceToken]:
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active.is_(True),
            DeviceToken.is_deleted.is_(False),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_active_tokens(
        self, *, limit: int = 500, offset: int = 0
    ) -> list[DeviceToken]:
        stmt = (
            select(DeviceToken)
            .where(
                DeviceToken.is_active.is_(True),
                DeviceToken.is_deleted.is_(False),
            )
            .order_by(DeviceToken.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        *,
        user_id: UUID,
        token: str,
        platform: str,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> DeviceToken:
        now = datetime.now(timezone.utc)
        existing = self.get_by_token(token)
        if existing:
            existing.user_id = user_id
            existing.platform = platform
            existing.device_id = device_id or existing.device_id
            existing.app_version = app_version or existing.app_version
            existing.last_seen_at = now
            existing.is_active = True
            existing.is_deleted = False
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = DeviceToken(
            user_id=user_id,
            token=token,
            platform=platform,
            device_id=device_id,
            app_version=app_version,
            last_seen_at=now,
            is_active=True,
            is_deleted=False,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def deactivate_token(self, token: str) -> bool:
        row = self.get_by_token(token)
        if not row:
            return False
        row.is_active = False
        self.db.add(row)
        self.db.commit()
        return True

    def deactivate_tokens(self, tokens: list[str]) -> int:
        if not tokens:
            return 0
        result = self.db.execute(
            update(DeviceToken)
            .where(DeviceToken.token.in_(tokens))
            .values(is_active=False)
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def deactivate_for_user_token(self, user_id: UUID, token: str) -> bool:
        row = self.get_by_token(token)
        if not row or row.user_id != user_id:
            return False
        row.is_active = False
        self.db.add(row)
        self.db.commit()
        return True
