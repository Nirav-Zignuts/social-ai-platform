from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.schemas.instagram_schema import (
    ConnectedAccountResponse,
    InstagramAccountMetrics,
    InstagramConnectResponse,
    InstagramConnectionStatusResponse,
)
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.core.redis import get_redis_client
from app.db.session import get_db
from app.integrations.meta.exceptions import MetaIntegrationError
from app.middlewares.auth_middleware import require_auth
from app.repositories.social_accounts import OAuthStateRepository
from app.services.instagram_oauth_service import InstagramOAuthService

router = APIRouter(tags=["Instagram"])


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


def _get_instagram_oauth_service(db: Session = Depends(get_db)) -> InstagramOAuthService:
    redis_client = get_redis_client()
    oauth_state_repo = OAuthStateRepository(redis_client)
    return InstagramOAuthService(db=db, oauth_state_repo=oauth_state_repo)


@router.get(
    "/workspaces/{workspace_id}/instagram",
    response_model=SuccessMessage,
    summary="Get workspace Instagram connection details",
)
async def get_instagram_connection(
    workspace_id: UUID,
    service: InstagramOAuthService = Depends(_get_instagram_oauth_service),
    current_user=Depends(require_auth),
):
    try:
        result = await service.get_connection(workspace_id, _user_id(current_user))
        account = result["account"]
        metrics = result.get("metrics")
        payload = InstagramConnectionStatusResponse(
            connected=result["connected"],
            account=ConnectedAccountResponse.model_validate(account) if account else None,
            metrics=InstagramAccountMetrics.model_validate(metrics) if metrics else None,
        )
        return SuccessMessage(
            message="Instagram connection retrieved successfully",
            data=payload.model_dump(mode="json"),
            code=status.HTTP_200_OK,
        )
    except HTTPException:
        raise
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get(
    "/workspaces/{workspace_id}/instagram/connect",
    response_model=SuccessMessage,
    summary="Start Instagram OAuth (returns Meta authorization URL)",
)
async def instagram_connect(
    workspace_id: UUID,
    service: InstagramOAuthService = Depends(_get_instagram_oauth_service),
    current_user=Depends(require_auth),
):
    try:
        result = await service.initiate_connect(workspace_id, _user_id(current_user))
        return SuccessMessage(
            message="Instagram OAuth URL generated successfully",
            data=InstagramConnectResponse.model_validate(result).model_dump(mode="json"),
            code=status.HTTP_200_OK,
        )
    except HTTPException:
        raise
    except MetaIntegrationError:
        raise
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.get(
    "/instagram/callback",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Instagram OAuth callback (redirects to frontend settings)",
)
async def instagram_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    service: InstagramOAuthService = Depends(_get_instagram_oauth_service),
):
    return await service.handle_callback(code=code, state=state, error=error)
