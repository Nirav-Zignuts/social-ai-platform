"""
Production FCM client (HTTP v1 via firebase-admin).

Mirrors common food-delivery patterns:
- lazy credential init (fail soft when push is disabled)
- multicast in chunks of 500
- topic send for all-users broadcasts
- invalid token collection for registry cleanup
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

FCM_MULTICAST_LIMIT = 500


@dataclass
class PushSendResult:
    success_count: int = 0
    failure_count: int = 0
    invalid_tokens: list[str] = field(default_factory=list)


class FCMClient:
    """Thin wrapper around firebase_admin.messaging."""

    def __init__(self) -> None:
        self._initialized = False
        self._available = False

    @property
    def is_available(self) -> bool:
        self._ensure_init()
        return self._available

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            logger.info("Push notifications disabled (PUSH_NOTIFICATIONS_ENABLED=false)")
            return

        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError:
            logger.error("firebase-admin is not installed; push delivery disabled")
            return

        try:
            if firebase_admin._apps:  # type: ignore[attr-defined]
                self._available = True
                return

            cred = None
            raw_json = (settings.FIREBASE_CREDENTIALS_JSON or "").strip()
            path = (settings.FIREBASE_CREDENTIALS_PATH or "").strip()
            if raw_json and raw_json not in {"{", "{}"}:
                cred = credentials.Certificate(json.loads(raw_json))
            elif path:
                if not os.path.isabs(path):
                    # Resolve relative to backend project root (…/backend), not cwd.
                    backend_root = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "..", "..")
                    )
                    path = os.path.join(backend_root, path)
                cred = credentials.Certificate(path)
            else:
                logger.warning(
                    "Push enabled but FIREBASE_CREDENTIALS_JSON / "
                    "FIREBASE_CREDENTIALS_PATH is missing"
                )
                return

            options: dict[str, Any] = {}
            project_id = (settings.FIREBASE_PROJECT_ID or "").strip()
            if project_id:
                options["projectId"] = project_id

            firebase_admin.initialize_app(cred, options or None)
            self._available = True
            logger.info("Firebase Admin initialized for FCM")
        except Exception:
            logger.exception("Failed to initialize Firebase Admin")
            self._available = False

    def send_to_tokens(
        self,
        tokens: list[str],
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushSendResult:
        result = PushSendResult()
        if not tokens:
            return result
        self._ensure_init()
        if not self._available:
            result.failure_count = len(tokens)
            return result

        from firebase_admin import messaging

        string_data = {k: str(v) for k, v in (data or {}).items() if v is not None}

        for start in range(0, len(tokens), FCM_MULTICAST_LIMIT):
            chunk = tokens[start : start + FCM_MULTICAST_LIMIT]
            message = messaging.MulticastMessage(
                tokens=chunk,
                notification=messaging.Notification(title=title, body=body),
                data=string_data or None,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1),
                    )
                ),
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                    ),
                ),
            )
            try:
                response = messaging.send_each_for_multicast(message)
            except Exception:
                logger.exception("FCM multicast failed for %s tokens", len(chunk))
                result.failure_count += len(chunk)
                continue

            result.success_count += response.success_count
            result.failure_count += response.failure_count
            for idx, send_response in enumerate(response.responses):
                if send_response.success:
                    continue
                if self._is_invalid_token(send_response.exception):
                    result.invalid_tokens.append(chunk[idx])

        return result

    def send_to_topic(
        self,
        topic: str,
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        self._ensure_init()
        if not self._available:
            return False

        from firebase_admin import messaging

        string_data = {k: str(v) for k, v in (data or {}).items() if v is not None}
        message = messaging.Message(
            topic=topic,
            notification=messaging.Notification(title=title, body=body),
            data=string_data or None,
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
            ),
        )
        try:
            messaging.send(message)
            return True
        except Exception:
            logger.exception("FCM topic send failed for topic=%s", topic)
            return False

    def subscribe_tokens_to_topic(self, tokens: list[str], topic: str) -> None:
        if not tokens:
            return
        self._ensure_init()
        if not self._available:
            logger.warning(
                "Skipping topic subscribe (FCM unavailable) topic=%s count=%s",
                topic,
                len(tokens),
            )
            return

        from firebase_admin import messaging

        for start in range(0, len(tokens), FCM_MULTICAST_LIMIT):
            chunk = tokens[start : start + FCM_MULTICAST_LIMIT]
            try:
                response = messaging.subscribe_to_topic(chunk, topic)
                logger.info(
                    "FCM topic subscribe topic=%s success=%s failure=%s",
                    topic,
                    response.success_count,
                    response.failure_count,
                )
            except Exception:
                logger.exception(
                    "FCM topic subscribe failed topic=%s count=%s",
                    topic,
                    len(chunk),
                )

    def unsubscribe_tokens_from_topic(self, tokens: list[str], topic: str) -> None:
        if not tokens:
            return
        self._ensure_init()
        if not self._available:
            return

        from firebase_admin import messaging

        for start in range(0, len(tokens), FCM_MULTICAST_LIMIT):
            chunk = tokens[start : start + FCM_MULTICAST_LIMIT]
            try:
                messaging.unsubscribe_from_topic(chunk, topic)
            except Exception:
                logger.exception(
                    "FCM topic unsubscribe failed topic=%s count=%s",
                    topic,
                    len(chunk),
                )

    @staticmethod
    def _is_invalid_token(exc: BaseException | None) -> bool:
        if exc is None:
            return False
        try:
            from firebase_admin.exceptions import NotFoundError
            from firebase_admin.messaging import UnregisteredError
        except ImportError:
            return False

        if isinstance(exc, (UnregisteredError, NotFoundError)):
            return True
        code = getattr(exc, "code", None)
        if code in {"NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"}:
            return True
        message = str(exc).lower()
        return any(
            needle in message
            for needle in (
                "requested entity was not found",
                "registration-token-not-registered",
                "invalid registration",
            )
        )


@lru_cache
def get_fcm_client() -> FCMClient:
    return FCMClient()
