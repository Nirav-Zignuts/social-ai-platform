from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_broadcast import NotificationBroadcast
from app.models.user import User
from app.core.enums import UserStatus
from app.repositories.base import BaseRepository


class NotificationBroadcastRepository(BaseRepository[NotificationBroadcast]):
    model = NotificationBroadcast

    def __init__(self, db: Session):
        super().__init__(db)

    def get(self, broadcast_id: UUID) -> NotificationBroadcast | None:
        stmt = select(NotificationBroadcast).where(
            NotificationBroadcast.id == broadcast_id,
            NotificationBroadcast.is_deleted.is_(False),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, row: NotificationBroadcast) -> NotificationBroadcast:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: NotificationBroadcast) -> NotificationBroadcast:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def iter_active_user_ids(self, *, batch_size: int = 500):
        """Yield batches of active, non-deleted user IDs."""
        offset = 0
        while True:
            stmt = (
                select(User.id)
                .where(
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                    User.status == UserStatus.ACTIVE,
                )
                .order_by(User.created_at.asc())
                .offset(offset)
                .limit(batch_size)
            )
            batch = list(self.db.execute(stmt).scalars().all())
            if not batch:
                break
            yield batch
            offset += batch_size
