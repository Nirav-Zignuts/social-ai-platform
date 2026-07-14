"""
Email sending via Resend HTTP API (works on Render Free; SMTP is blocked there).
"""

from __future__ import annotations

import logging
from typing import Optional

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service responsible for sending email messages through Resend."""

    def __init__(self) -> None:
        self.api_key = (settings.RESEND_API_KEY or "").strip()
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
        """Send an email using Resend."""
        if not self.api_key:
            raise RuntimeError(
                "RESEND_API_KEY is not configured. Add it in Render/env before sending email."
            )
        if not self.email_from:
            raise RuntimeError(
                "EMAIL_FROM is not configured. Use a Resend-verified sender, "
                "e.g. 'AI Platform <onboarding@resend.dev>' for testing."
            )

        resend.api_key = self.api_key
        params: resend.Emails.SendParams = {
            "from": self.email_from,
            "to": [recipient],
            "subject": subject,
            "html": html_body,
        }
        if text_body:
            params["text"] = text_body

        try:
            result = resend.Emails.send(params)
            email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
            logger.info(
                "Email sent via Resend to %s (id=%s)",
                recipient,
                email_id,
            )
        except Exception:
            logger.exception("Failed to send email to %s via Resend", recipient)
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
