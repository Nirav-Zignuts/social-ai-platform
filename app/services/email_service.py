"""
Reusable email sending service.
"""

import ssl
from email.message import EmailMessage
from typing import Optional

import smtplib

from app.core.config import settings


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
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
            smtp.starttls(context=context)
            smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)

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
