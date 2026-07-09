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
            # SSL (recommended for Gmail - port 465)
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    context=context,
                ) as smtp:
                    smtp.login(self.smtp_username, self.smtp_password)
                    smtp.send_message(message)

            # STARTTLS (port 587)
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
        subject = "Verify your email address"
        text_body = (
            f"Hi {full_name},\n\n"
            "Please verify your email address by clicking the link below:\n"
            f"{verification_link}\n\n"
            "If you did not request this, please ignore this email."
        )
        html_body = (
            f"<p>Hi {full_name},</p>"
            f"<p>Please verify your email address by clicking the link below:</p>"
            f"<p><a href=\"{verification_link}\">Verify email</a></p>"
            "<p>If you did not request this, please ignore this email.</p>"
        )
        self.send_email(recipient, subject, html_body, text_body)

    def send_post_notification_email(
        self,
        recipient: str,
        full_name: str,
        subject: str,
        message: str,
        review_link: str | None = None,
    ) -> None:
        """Send a post-generation or review notification email."""
        text_body = f"Hi {full_name},\n\n{message}\n"
        html_body = f"<p>Hi {full_name},</p><p>{message}</p>"

        if review_link:
            text_body += f"\nReview your post: {review_link}\n"
            html_body += f'<p><a href="{review_link}">Review your post</a></p>'

        self.send_email(recipient, subject, html_body, text_body)

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
