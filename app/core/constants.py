"""
Constants for the application.
"""

# Token Types
TOKEN_TYPE_BEARER = "bearer"
TOKEN_TYPE_REFRESH = "refresh"

# Token Algorithm
ALGORITHM = "RS256"

# Token Subjects
TOKEN_SUBJECT_ACCESS = "access"
TOKEN_SUBJECT_REFRESH = "refresh"
TOKEN_SUBJECT_ACTIVATION = "activation"

# Time related constants (in seconds)
EMAIL_VERIFICATION_EXPIRE_SECONDS = 86400  # 24 hours
PASSWORD_RESET_EXPIRE_SECONDS = 3600  # 1 hour

# Auth Constants
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Common status codes
SUCCESS_STATUS = "success"
ERROR_STATUS = "error"
