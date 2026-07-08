from uuid import UUID

from sqlalchemy import select

from app.core.enums import AuthProvider
from app.models.user_auth_provider import UserAuthProvider
from app.repositories.base import BaseRepository


class UserAuthProviderRepository(
    BaseRepository[UserAuthProvider]
):

    model = UserAuthProvider


    def get_local_provider(
        self,
        user_id: UUID,
    ) -> UserAuthProvider | None:

        stmt = select(
            UserAuthProvider
        ).where(
            UserAuthProvider.user_id == user_id,
            UserAuthProvider.provider == AuthProvider.LOCAL,
        )

        result = self.db.execute(stmt)

        return result.scalar_one_or_none()