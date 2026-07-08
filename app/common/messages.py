"""
Response message definitions for the application.
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessMessage(BaseModel, Generic[T]):
    """
    Standard success response message.
    """

    status: str = "success"
    message: str
    data: Optional[T] = None
    code: int = 200

    def __init__(
        self, message: str, data: Optional[T] = None, code: int = 200, **kwargs
    ):
        super().__init__(
            message=message,
            data=data,
            code=code,
            **kwargs,
        )


class ErrorMessage(BaseModel):
    """
    Standard error response message.
    """

    status: str = "error"
    message: str
    code: int = 400
    details: Optional[Any] = None

    def __init__(
        self, message: str, code: int = 400, details: Optional[Any] = None, **kwargs
    ):
        super().__init__(
            message=message,
            code=code,
            details=details,
            **kwargs,
        )


# Common success messages
class AuthMessages:
    """Authentication related messages."""

    LOGIN_SUCCESS = "Login successful"
    LOGOUT_SUCCESS = "Logout successful"
    TOKEN_REFRESHED = "Token refreshed successfully"
    PASSWORD_CHANGED = "Password changed successfully"
    EMAIL_VERIFIED = "Email verified successfully"
    EMAIL_VERIFICATION_SENT = "Verification email sent"
    PASSWORD_RESET_SENT = "Password reset link sent to email"
    PASSWORD_RESET_SUCCESS = "Password reset successful"
    REGISTRATION_SUCCESS = "Registration successful"
    EMAIL_VERIFICATION_SENT = "Verification email sent"
    EMAIL_VERIFIED = "Email verified successfully"
    USER_RETRIEVED = "User retrieved successfully"


class ErrorMessages:
    """Error messages."""

    INVALID_CREDENTIALS = "Invalid email or password"
    USER_NOT_FOUND = "User not found"
    EMAIL_ALREADY_EXISTS = "Email already exists"
    INVALID_TOKEN = "Invalid or expired token"
    INVALID_ACTIVATION_TOKEN = "Invalid activation token"
    EMAIL_ALREADY_VERIFIED = "Email is already verified"
    EMAIL_NOT_VERIFIED = "Email address is not verified"
    UNAUTHORIZED = "Unauthorized access"
    FORBIDDEN = "Forbidden access"
    RESOURCE_NOT_FOUND = "Resource not found"
    INVALID_REQUEST = "Invalid request"
    SERVER_ERROR = "Internal server error"
    TOKEN_EXPIRED = "Token has expired"
    INVALID_TOKEN_TYPE = "Invalid token type"
    PASSWORD_MISMATCH = "Password does not match"
    WEAK_PASSWORD = "Password is too weak"
