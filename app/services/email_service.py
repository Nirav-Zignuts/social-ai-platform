"""
Reusable email sending service.
"""

import logging
import ssl
from email.message import EmailMessage
from typing import Optional

import smtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service responsible for sending email messages."""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM
        self.frontend_url = settings.FRONTEND_URL

    def build_verification_link(self, token: str) -> str:
        """Build the frontend email verification URL."""
        return f"{self.frontend_url.rstrip('/')}/verify-email?token={token}"

    def _connect(self) -> smtplib.SMTP:
        context = ssl.create_default_context()
        use_ssl = self.smtp_port == 465

        if use_ssl:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                self.smtp_host, self.smtp_port, context=context
            )
        else:
            smtp = smtplib.SMTP(self.smtp_host, self.smtp_port)

        smtp.ehlo()

        if not use_ssl and smtp.has_extn("STARTTLS"):
            smtp.starttls(context=context)
            smtp.ehlo()

        if self.smtp_username and smtp.has_extn("AUTH"):
            smtp.login(self.smtp_username, self.smtp_password)
        elif self.smtp_username:
            logger.warning(
                "SMTP credentials configured but server does not support AUTH; sending without login"
            )

        return smtp

    def send_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> None:
        """Send an email using SMTP."""
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.email_from
        message["To"] = recipient
        message.set_content(text_body or html_body)
        message.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()

        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    context=context,
                ) as smtp:
                    smtp.login(self.smtp_username, self.smtp_password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    smtp.login(self.smtp_username, self.smtp_password)
                    smtp.send_message(message)

            logger.info("Email sent successfully to %s", recipient)
        except Exception:
            logger.exception("Failed to send email to %s", recipient)
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
