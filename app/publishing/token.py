from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import ConnectedAccountStatus, SocialProvider
from app.integrations.meta.exceptions import InstagramTokenExpiredError
from app.models.connected_account import ConnectedAccount
from app.repositories.social_accounts import ConnectedAccountRepository


def get_valid_token(db: Session, workspace_id: UUID) -> ConnectedAccount:
    """
    Return the workspace Instagram connected account if the token is usable.

    Raises InstagramTokenExpiredError when missing, disconnected, or past expires_at.
    """
    account = ConnectedAccountRepository(db).get_by_workspace_and_provider(
        workspace_id=workspace_id,
        provider=SocialProvider.INSTAGRAM.value,
    )
    if not account or not account.access_token:
        raise InstagramTokenExpiredError("Instagram is not connected for this workspace.")

    if account.status != ConnectedAccountStatus.CONNECTED.value:
        raise InstagramTokenExpiredError("Instagram connection is not active.")

    if account.expires_at is not None:
        expires_at = account.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise InstagramTokenExpiredError("Instagram token expired.")

    if not account.instagram_business_account_id:
        raise InstagramTokenExpiredError(
            "Instagram Business Account ID is missing. Please reconnect Instagram."
        )

    return account
