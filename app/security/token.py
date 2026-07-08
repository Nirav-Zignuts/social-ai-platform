"""
JWT token handling with RSA encryption.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.core.config import settings
from app.core.constants import (
    ALGORITHM,
    EMAIL_VERIFICATION_EXPIRE_SECONDS,
    TOKEN_SUBJECT_ACCESS,
    TOKEN_SUBJECT_ACTIVATION,
    TOKEN_SUBJECT_REFRESH,
)


class TokenError(Exception):
    """Base exception for token errors."""

    pass


class TokenExpiredError(TokenError):
    """Token has expired."""

    pass


class InvalidTokenError(TokenError):
    """Token is invalid."""

    pass


class TokenManager:
    """
    Manages JWT token creation and validation using RSA encryption.
    """

    def __init__(self):
        self.private_key = settings.RSA_PRIVATE_KEY
        self.public_key = settings.RSA_PUBLIC_KEY
        self.algorithm = ALGORITHM

    def create_access_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create an access token.

        Args:
            subject: The subject of the token (usually user ID)
            expires_delta: Custom expiration time
            additional_claims: Additional claims to include in the token

        Returns:
            Encoded JWT token
        """
        return self._create_token(
            subject=subject,
            token_type=TOKEN_SUBJECT_ACCESS,
            expires_delta=expires_delta,
            additional_claims=additional_claims,
        )

    def create_refresh_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a refresh token.

        Args:
            subject: The subject of the token (usually user ID)
            expires_delta: Custom expiration time
            additional_claims: Additional claims to include in the token

        Returns:
            Encoded JWT token
        """
        return self._create_token(
            subject=subject,
            token_type=TOKEN_SUBJECT_REFRESH,
            expires_delta=expires_delta,
            additional_claims=additional_claims,
        )

    def create_activation_token(
        self,
        subject: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create an email activation token.

        Args:
            subject: The subject of the token (usually user ID)
            expires_delta: Custom expiration time
            additional_claims: Additional claims to include in the token

        Returns:
            Encoded JWT token
        """
        return self._create_token(
            subject=subject,
            token_type=TOKEN_SUBJECT_ACTIVATION,
            expires_delta=expires_delta,
            additional_claims=additional_claims,
        )

    def _create_token(
        self,
        subject: str,
        token_type: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Internal method to create a token.

        Args:
            subject: The subject of the token
            token_type: Type of token (access or refresh)
            expires_delta: Custom expiration time
            additional_claims: Additional claims to include

        Returns:
            Encoded JWT token
        """
        if expires_delta:
            expires = datetime.now(timezone.utc) + expires_delta
        else:
            if token_type == TOKEN_SUBJECT_ACCESS:
                expires = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            elif token_type == TOKEN_SUBJECT_REFRESH:
                expires = datetime.now(timezone.utc) + timedelta(
                    days=settings.REFRESH_TOKEN_EXPIRE_DAYS
                )
            elif token_type == TOKEN_SUBJECT_ACTIVATION:
                expires = datetime.now(timezone.utc) + timedelta(
                    seconds=EMAIL_VERIFICATION_EXPIRE_SECONDS
                )
            else:
                expires = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )

        payload = {
            "sub": subject,
            "type": token_type,
            "exp": expires,
            "iat": datetime.now(timezone.utc),
        }

        if additional_claims:
            payload.update(additional_claims)

        encoded_jwt = jwt.encode(
            payload, self._normalize_pem(self.private_key), algorithm=self.algorithm
        )
        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a token.

        Args:
            token: The JWT token to decode

        Returns:
            Decoded token payload

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token, self._normalize_pem(self.public_key), algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError("Invalid token") from e
        except Exception as e:
            raise InvalidTokenError(f"Token validation failed: {str(e)}") from e

    def get_subject_from_token(self, token: str) -> str:
        """
        Extract the subject (user ID) from a token.

        Args:
            token: The JWT token

        Returns:
            The subject claim from the token

        Raises:
            TokenError: If token is invalid
        """
        try:
            payload = self.decode_token(token)
            subject = payload.get("sub")
            if not subject:
                raise InvalidTokenError("Token does not contain subject")
            return subject
        except TokenError:
            raise

    def validate_token_type(self, token: str, expected_type: str) -> bool:
        """
        Validate that a token matches the expected type.

        Args:
            token: The JWT token
            expected_type: The expected token type

        Returns:
            True if token type matches

        Raises:
            TokenError: If token is invalid or type doesn't match
        """
        payload = self.decode_token(token)
        token_type = payload.get("type")
        if token_type != expected_type:
            raise InvalidTokenError(
                f"Invalid token type. Expected {expected_type}, got {token_type}"
            )
        return True

    def _normalize_pem(self,value: str | None) -> str:
        """Normalize PEM values passed through environment variables or AWS Secrets Manager."""
        return (value or "").replace("\\n", "\n").strip()
# Global token manager instance
token_manager = TokenManager()
