from enum import Enum


class UserStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class AuthProvider(str, Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
class GeneratedPostStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEWER_PASSED = "REVIEWER_PASSED"
    REVIEWER_FAILED = "REVIEWER_FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class PostReviewAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REGENERATE = "REGENERATE"
    SKIP = "SKIP"
    EDIT = "EDIT"

class PublishingJobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class NotificationType(str, Enum):
    POST_READY_FOR_REVIEW = "post_ready_for_review"
    POST_REGENERATED = "post_regenerated"
    POST_APPROVED = "post_approved"
    POST_REJECTED = "post_rejected"
    POST_AUTO_APPROVED = "post_auto_approved"
    INSTAGRAM_TOKEN_EXPIRED = "instagram_token_expired"
    POST_PUBLISH_FAILED = "post_publish_failed"
    POST_PUBLISH_SUCCEEDED = "post_publish_succeeded"
    BILLING_PAYMENT_FAILED = "billing_payment_failed"
    BILLING_WORKSPACES_LOCKED = "billing_workspaces_locked"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"


class SocialProvider(str, Enum):
    INSTAGRAM = "instagram"


class ConnectedAccountStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WorkspaceStatus(str, Enum):
    """Workspace lifecycle status (string column; not a Postgres enum)."""

    ACTIVE = "active"
    # Exceeds plan workspace_limit after downgrade — skipped by gen/publish pollers.
    LOCKED_OVER_LIMIT = "locked_over_limit"
    DELETED = "deleted"
