import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.admin import Admin, AdminOTPCode
from app.repositories.admin_auth import AdminAuthRepository
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

MAX_OTP_ATTEMPTS = 5
MAX_OTP_REQUESTS_PER_WINDOW = 3
OTP_REQUEST_WINDOW_MINUTES = 15


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _otp_hash(admin_id: UUID, code: str) -> str:
    pepper = settings.ADMIN_OTP_PEPPER
    if not pepper:
        raise RuntimeError("ADMIN_OTP_PEPPER is not configured")
    message = f"{admin_id}:{code}".encode()
    return hmac.new(pepper.encode(), message, hashlib.sha256).hexdigest()


def _jwe_key() -> bytes:
    secret = settings.ADMIN_JWE_SECRET
    if not secret:
        raise RuntimeError("ADMIN_JWE_SECRET is not configured")
    # A256GCM with direct encryption requires exactly 256 key bits. Hashing the
    # dedicated high-entropy env secret gives a stable 32-byte encryption key.
    return hashlib.sha256(secret.encode()).digest()


def mint_admin_token(admin: Admin) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ADMIN_SESSION_EXPIRE_MINUTES)
    payload = {
        "admin_id": str(admin.id),
        "email": admin.email,
        "issued_at": int(now.timestamp()),
        "expires_at": int(expires_at.timestamp()),
        "token_type": "admin_session",
    }
    token = jwe.encrypt(
        json.dumps(payload).encode(),
        _jwe_key(),
        algorithm="dir",
        encryption="A256GCM",
    )
    return token.decode() if isinstance(token, bytes) else token


def decrypt_admin_token(token: str) -> dict:
    plaintext = jwe.decrypt(token, _jwe_key())
    payload = json.loads(plaintext.decode())
    if payload.get("token_type") != "admin_session":
        raise ValueError("Invalid admin token type")
    expires_at = int(payload.get("expires_at") or 0)
    if expires_at <= int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Admin token expired")
    UUID(str(payload["admin_id"]))
    return payload


class AdminAuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AdminAuthRepository(db)

    def request_otp(self, email: str) -> None:
        normalized = _normalize_email(email)
        admin = self.repository.get_active_by_email(normalized, for_update=True)
        if not admin:
            return

        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=OTP_REQUEST_WINDOW_MINUTES
        )
        recent_count = self.repository.count_codes_since(admin.id, window_start)
        if recent_count >= MAX_OTP_REQUESTS_PER_WINDOW:
            return

        self.repository.consume_active_codes(admin.id)

        code = f"{secrets.randbelow(1_000_000):06d}"
        otp = AdminOTPCode(
            admin_id=admin.id,
            code_hash=_otp_hash(admin.id, code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.ADMIN_OTP_EXPIRE_MINUTES),
        )
        self.repository.add_code(otp)
        self.db.commit()

        try:
            EmailService().send_email(
                recipient=admin.email,
                subject="Your admin sign-in code",
                html_body=(
                    "<p>Your administrator sign-in code is:</p>"
                    f"<p style='font-size:24px;font-weight:bold'>{code}</p>"
                    f"<p>It expires in {settings.ADMIN_OTP_EXPIRE_MINUTES} minutes. "
                    "If you did not request this code, ignore this email.</p>"
                ),
                text_body=(
                    f"Your administrator sign-in code is {code}. "
                    f"It expires in {settings.ADMIN_OTP_EXPIRE_MINUTES} minutes."
                ),
            )
        except Exception:
            logger.exception("Failed to deliver admin OTP admin_id=%s", admin.id)
            otp.consumed = True
            self.db.commit()

    def verify_otp(self, email: str, code: str) -> str | None:
        normalized = _normalize_email(email)
        admin = self.repository.get_active_by_email(normalized)
        if not admin:
            return None

        now = datetime.now(timezone.utc)
        otp = self.repository.get_latest_valid_code(admin.id, now)
        if not otp or otp.attempt_count >= MAX_OTP_ATTEMPTS:
            return None

        valid = hmac.compare_digest(otp.code_hash, _otp_hash(admin.id, code))
        if not valid:
            otp.attempt_count += 1
            if otp.attempt_count >= MAX_OTP_ATTEMPTS:
                otp.consumed = True
            self.db.commit()
            return None

        # Re-check immediately before token minting; do not trust the earlier row.
        self.db.refresh(admin)
        if not admin.is_active or admin.is_deleted:
            return None

        otp.consumed = True
        self.db.commit()
        return mint_admin_token(admin)


def request_admin_otp_in_background(email: str) -> None:
    """Use an independent session so the public response has uniform timing."""
    with SessionLocal() as db:
        AdminAuthService(db).request_otp(email)
