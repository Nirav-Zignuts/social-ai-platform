class MetaIntegrationError(Exception):
    """Base exception for Meta integration errors."""


class MetaAPIError(MetaIntegrationError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}


class OAuthStateExpired(MetaIntegrationError):
    """OAuth state token has expired."""


class OAuthStateInvalid(MetaIntegrationError):
    """OAuth state token is invalid or already used."""


class InstagramAccountNotFound(MetaIntegrationError):
    """No Instagram Business Account linked to the user's Facebook Pages."""


class FacebookPageNotFound(MetaIntegrationError):
    """No Facebook Pages found for the authorized user."""
