import secrets
from datetime import datetime, timezone

from app.integrations.google.exceptions import GoogleOAuthStateExpired, GoogleOAuthStateInvalid
from app.integrations.google.schemas import GoogleOAuthStatePayload

GOOGLE_OAUTH_STATE_PREFIX = "google_oauth_state:"
GOOGLE_OAUTH_STATE_TTL_SECONDS = 600


class GoogleOAuthStateRepository:
    """Redis-backed OAuth state for Google login."""

    def __init__(self, redis_client) -> None:
        self.redis = redis_client

    def _key(self, state: str) -> str:
        return f"{GOOGLE_OAUTH_STATE_PREFIX}{state}"

    async def create(
        self,
        *,
        redirect_url: str,
        fcm_token: str | None = None,
    ) -> str:
        state = secrets.token_urlsafe(32)
        payload = GoogleOAuthStatePayload(
            redirect_url=redirect_url,
            fcm_token=fcm_token,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self.redis.setex(
            self._key(state),
            GOOGLE_OAUTH_STATE_TTL_SECONDS,
            payload.model_dump_json(),
        )
        return state

    async def consume(self, state: str) -> GoogleOAuthStatePayload:
        key = self._key(state)
        raw = await self.redis.get(key)
        if not raw:
            raise GoogleOAuthStateExpired("OAuth state has expired or is invalid.")

        payload = GoogleOAuthStatePayload.model_validate_json(raw)

        if payload.provider != "google":
            await self.redis.delete(key)
            raise GoogleOAuthStateInvalid("OAuth state provider mismatch.")

        await self.redis.delete(key)
        return payload
