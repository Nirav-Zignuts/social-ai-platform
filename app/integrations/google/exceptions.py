class GoogleIntegrationError(Exception):
    """Base exception for Google OAuth integration."""


class GoogleOAuthStateExpired(GoogleIntegrationError):
    """OAuth state token has expired or is missing."""


class GoogleOAuthStateInvalid(GoogleIntegrationError):
    """OAuth state token is invalid or already used."""


class GoogleAPIError(GoogleIntegrationError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GoogleRedirectNotAllowed(GoogleIntegrationError):
    """Frontend redirect URL is not in the allowlist."""
