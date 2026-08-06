"""Device token registration / unregistration for push delivery."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.firebase.fcm_client import get_fcm_client
from app.repositories.device_token import DeviceTokenRepository

logger = logging.getLogger(__name__)

ALLOWED_PLATFORMS = {"web", "ios", "android"}


class DeviceTokenService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DeviceTokenRepository(db)

    def register(
        self,
        user_id: UUID,
        *,
        fcm_token: str,
        platform: str = "web",
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> dict:
        token = (fcm_token or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="fcm_token is required")

        normalized_platform = (platform or "web").strip().lower()
        if normalized_platform not in ALLOWED_PLATFORMS:
            raise HTTPException(
                status_code=400,
                detail=f"platform must be one of: {', '.join(sorted(ALLOWED_PLATFORMS))}",
            )

        row = self.repo.upsert(
            user_id=user_id,
            token=token,
            platform=normalized_platform,
            device_id=(device_id or "").strip() or None,
            app_version=(app_version or "").strip() or None,
        )

        topic = (settings.FCM_ALL_USERS_TOPIC or "").strip()
        if topic:
            try:
                get_fcm_client().subscribe_tokens_to_topic([token], topic)
            except Exception:
                logger.exception("Failed to subscribe device to topic %s", topic)

        return {
            "id": str(row.id),
            "platform": row.platform,
            "device_id": row.device_id,
            "app_version": row.app_version,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }

    def unregister(self, user_id: UUID, *, fcm_token: str) -> None:
        token = (fcm_token or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="fcm_token is required")

        deactivated = self.repo.deactivate_for_user_token(user_id, token)
        if not deactivated:
            raise HTTPException(status_code=404, detail="Device token not found")

        topic = (settings.FCM_ALL_USERS_TOPIC or "").strip()
        if topic:
            try:
                get_fcm_client().unsubscribe_tokens_from_topic([token], topic)
            except Exception:
                logger.exception("Failed to unsubscribe device from topic %s", topic)

    def register_if_present(
        self,
        user_id: UUID,
        fcm_token: str | None,
        *,
        platform: str | None = None,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> None:
        """Best-effort upsert used from login / update-fcm paths."""
        token = (fcm_token or "").strip()
        if not token:
            return
        try:
            self.register(
                user_id,
                fcm_token=token,
                platform=platform or "web",
                device_id=device_id,
                app_version=app_version,
            )
        except Exception:
            logger.exception("Failed to register device token for user %s", user_id)
