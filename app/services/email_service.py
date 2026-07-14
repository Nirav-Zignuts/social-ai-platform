"""
Email sending via Brevo HTTP API (works on Render Free; SMTP ports are blocked there).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
_FROM_RE = re.compile(r"^(.*?)\s*<([^>]+)>\s*$")


def _parse_from_address(value: str) -> tuple[str, str]:
    """Parse 'Name <email@x.com>' or bare email into (name, email)."""
    raw = (value or "").strip()
    if not raw:
        return "", ""
    match = _FROM_RE.match(raw)
    if match:
        name = match.group(1).strip().strip('"') or "AI Marketing Platform"
        return name, match.group(2).strip()
    return "AI Marketing Platform", raw


class EmailService:
    """Service responsible for sending email messages through Brevo."""

    def __init__(self) -> None:
        self.api_key = (settings.BREVO_API_KEY or "").strip()
        self.email_from = (settings.EMAIL_FROM or "").strip()
        self.frontend_url = settings.FRONTEND_URL

    def build_verification_link(self, token: str) -> str:
        """Build the frontend email verification URL."""
        return f"{self.frontend_url.rstrip('/')}/verify-email?token={token}"

    def send_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> None:
        """Send an email using Brevo transactional API."""
        if not self.api_key:
            raise RuntimeError(
                "BREVO_API_KEY is not configured. Add it in Render/env before sending email."
            )
        if not self.email_from:
            raise RuntimeError(
                "EMAIL_FROM is not configured. Use a Brevo-verified sender, "
                "e.g. 'AI Marketing Platform <noreply@yourdomain.com>'."
            )

        sender_name, sender_email = _parse_from_address(self.email_from)
        if not sender_email:
            raise RuntimeError(
                "EMAIL_FROM must include a valid email, e.g. "
                "'AI Marketing Platform <noreply@yourdomain.com>'."
            )

        payload: dict = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_body,
        }
        if text_body:
            payload["textContent"] = text_body

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    BREVO_SEND_URL,
                    headers={
                        "api-key": self.api_key,
                        "accept": "application/json",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                logger.error(
                    "Brevo send failed status=%s body=%s",
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            data = response.json() if response.content else {}
            message_id = data.get("messageId")
            logger.info(
                "Email sent via Brevo to %s (messageId=%s)",
                recipient,
                message_id,
            )
        except Exception:
            logger.exception("Failed to send email to %s via Brevo", recipient)
            raise

    def send_verification_email(
        self,
        recipient: str,
        full_name: str,
        verification_link: str,
    ) -> None:
        """Send the email verification message."""
        from app.services.email_templates import verification_email

        rendered = verification_email(
            full_name=full_name,
            verification_link=verification_link,
        )
        self.send_email(
            recipient,
            rendered.subject,
            rendered.html_body,
            rendered.text_body,
        )

    def send_post_notification_email(
        self,
        recipient: str,
        full_name: str,
        subject: str,
        message: str,
        review_link: str | None = None,
        *,
        notification_type: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Send a product notification email using branded templates."""
        from app.services.email_templates import (
            generic_notification_email,
            render_notification_email,
        )

        data = dict(payload or {})
        data.setdefault("message", message)
        if review_link and "review_link" not in data and "settings_link" not in data:
            data["review_link"] = review_link

        if notification_type:
            rendered = render_notification_email(
                notification_type=notification_type,
                full_name=full_name,
                payload=data,
                subject=subject,
            )
        else:
            rendered = generic_notification_email(
                full_name=full_name,
                subject=subject,
                message=message,
                cta_url=review_link,
                cta_label="Open in app",
            )

        self.send_email(
            recipient,
            rendered.subject,
            rendered.html_body,
            rendered.text_body,
        )

    def send_verification_email_safe(
        self,
        recipient: str,
        full_name: str,
        verification_link: str,
    ) -> None:
        """Send verification email; log failures without raising (for background tasks)."""
        try:
            self.send_verification_email(recipient, full_name, verification_link)
        except Exception:
            logger.exception(
                "Background verification email failed for %s", recipient
            )
