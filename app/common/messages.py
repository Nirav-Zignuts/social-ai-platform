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
    FCM_TOKEN_UPDATED = "FCM token updated successfully"
    DEVICE_REGISTERED = "Device registered for push notifications"
    DEVICE_UNREGISTERED = "Device unregistered from push notifications"
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
    RATE_LIMIT_EXCEEDED = "Too many requests. Please try again later."
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


class AdminMessages:
    OTP_REQUESTED = "If this email is registered as an admin, a code has been sent."
    OTP_VERIFIED = "Admin authentication successful"
    ENQUIRIES_RETRIEVED = "Contact enquiries retrieved successfully"
    ENQUIRY_RETRIEVED = "Contact enquiry retrieved successfully"
    ENQUIRY_UPDATED = "Contact enquiry updated successfully"
    ENQUIRY_DELETED = "Contact enquiry deleted successfully"
    AI_USAGE_RETRIEVED = "AI usage logs retrieved successfully"
    AI_USAGE_SUMMARY_RETRIEVED = "AI usage summary retrieved successfully"
    USERS_RETRIEVED = "Users retrieved successfully"
    USER_RETRIEVED = "User support details retrieved successfully"
    WORKSPACE_RETRIEVED = "Workspace support details retrieved successfully"
    GENERATION_RUNS_RETRIEVED = "Generation runs retrieved successfully"
    PLAN_UPDATED = "User plan updated successfully"
    SUBSCRIPTION_STATUS_UPDATED = "Subscription status updated successfully"
    WORKSPACE_UNLOCKED = "Workspace unlocked successfully"
    PUBLISH_RETRY_QUEUED = "Publishing retry queued successfully"
    ACTION_LOGS_RETRIEVED = "Admin action logs retrieved successfully"
    BROADCAST_QUEUED = "Notification broadcast queued successfully"
    BROADCAST_RETRIEVED = "Notification broadcast retrieved successfully"


class ContactMessages:
    ENQUIRY_SUBMITTED = "Your enquiry has been submitted."
    SUPPORT_ISSUE_SUBMITTED = "Your support issue has been submitted."


class AdminErrorMessages:
    NOT_FOUND = "Not found"
    INVALID_OTP = "Invalid or expired code."
    ADMIN_NOT_FOUND = "Admin not found"
    ENQUIRY_NOT_FOUND = "Enquiry not found"
    PLAN_NOT_FOUND = "Plan not found"
    SUBSCRIPTION_NOT_FOUND = "Subscription not found"
    PUBLISHING_JOB_NOT_FOUND = "Publishing job not found"
    GENERATED_POST_NOT_FOUND = "Generated post not found"
    WORKSPACE_MUST_BE_ACTIVE = (
        "The workspace must be active before retrying publication."
    )
    PUBLISH_JOB_NOT_RETRYABLE = (
        "Only failed or retrying publishing jobs can be retried."
    )
    PUBLISH_ALREADY_ACTIVE = (
        "This post already has a processing or published job and cannot be manually retried."
    )
    POST_ALREADY_PUBLISHED = "Post is already published."
