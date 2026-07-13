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
    POST_APPROVED = "post_approved"
    POST_REJECTED = "post_rejected"
    POST_AUTO_APPROVED = "post_auto_approved"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"


class SocialProvider(str, Enum):
    INSTAGRAM = "instagram"


class ConnectedAccountStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
