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
    INVALID_CRON_SECRET = "Invalid or missing cron secret"
    SESSION_NOT_FOUND = "Session not found or logged out"
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
    WORKSPACE_NOT_FOUND = "Workspace not found"
    BUSINESS_PROFILE_NOT_FOUND = "Business profile not found for the given workspace"
    AI_CONFIG_NOT_FOUND = "AI configuration not found for the given workspace"
    DOCUMENT_NOT_FOUND = "Document not found"


class WorkspaceMessages:
    """Workspace related messages."""

    WORKSPACE_CREATED = "Workspace created successfully"
    WORKSPACES_RETRIEVED = "Workspaces retrieved successfully"
    WORKSPACE_RETRIEVED = "Workspace retrieved successfully"
    WORKSPACE_UPDATED = "Workspace updated successfully"
    WORKSPACE_DELETED = "Workspace deleted successfully"
    BUSINESS_PROFILE_UPSERTED = "Business profile saved successfully"
    BUSINESS_PROFILE_RETRIEVED = "Business profile retrieved successfully"
    AI_CONFIG_UPSERTED = "AI configuration saved successfully"
    AI_CONFIG_RETRIEVED = "AI configuration retrieved successfully"
    DOCUMENT_UPLOADED = "Document uploaded successfully"
    DOCUMENTS_RETRIEVED = "Documents retrieved successfully"
    DOCUMENT_DELETED = "Document deleted successfully"
    POST_DELETED = "Generated post deleted successfully"
    INSTAGRAM_DISCONNECTED = "Instagram disconnected successfully"
