import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.core.enums import SocialProvider
from app.integrations.meta.schemas import OAuthStatePayload
from app.integrations.meta.exceptions import OAuthStateExpired, OAuthStateInvalid
from app.models.connected_account import ConnectedAccount
from app.repositories.base import BaseRepository


OAUTH_STATE_PREFIX = "oauth_state:"
OAUTH_STATE_TTL_SECONDS = 600


class OAuthStateRepository:
    """Redis-backed OAuth state persistence."""

    def __init__(self, redis_client) -> None:
        self.redis = redis_client

    def _key(self, state: str) -> str:
        return f"{OAUTH_STATE_PREFIX}{state}"

    async def create(
        self,
        workspace_id: UUID,
        provider: SocialProvider,
        user_id: UUID,
    ) -> str:
        state = secrets.token_urlsafe(32)
        payload = OAuthStatePayload(
            workspace_id=str(workspace_id),
            provider=provider.value,
            user_id=str(user_id),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self.redis.setex(
            self._key(state),
            OAUTH_STATE_TTL_SECONDS,
            payload.model_dump_json(),
        )
        return state

    async def consume(self, state: str, provider: SocialProvider) -> OAuthStatePayload:
        key = self._key(state)
        raw = await self.redis.get(key)
        if not raw:
            raise OAuthStateExpired("OAuth state has expired or is invalid.")

        payload = OAuthStatePayload.model_validate_json(raw)

        if payload.provider != provider.value:
            await self.redis.delete(key)
            raise OAuthStateInvalid("OAuth state provider mismatch.")

        await self.redis.delete(key)
        return payload


class ConnectedAccountRepository(BaseRepository[ConnectedAccount]):
    model = ConnectedAccount

    def get_by_workspace_and_provider(
        self,
        workspace_id: UUID,
        provider: str,
    ) -> Optional[ConnectedAccount]:
        stmt = select(self.model).where(
            self.model.workspace_id == workspace_id,
            self.model.provider == provider,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_connected_account(
        self,
        workspace_id: UUID,
        provider: str,
        account_data: dict,
    ) -> ConnectedAccount:
        existing = self.get_by_workspace_and_provider(workspace_id, provider)
        if existing:
            for key, value in account_data.items():
                setattr(existing, key, value)
            return self.update(existing)

        account = ConnectedAccount(workspace_id=workspace_id, provider=provider, **account_data)
        return self.create(account)
