from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.db.session import get_db
from app.integrations.google.exceptions import GoogleRedirectNotAllowed
from app.repositories.google_oauth_state import GoogleOAuthStateRepository
from app.services.google_oauth_service import GoogleOAuthService

router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])


def get_google_oauth_service(db: Session = Depends(get_db)) -> GoogleOAuthService:
    print("[google_oauth_routes] get_google_oauth_service")
    try:
        redis_client = get_redis_client()
        print("[google_oauth_routes] redis_client ->", redis_client)
        oauth_state_repo = GoogleOAuthStateRepository(redis_client)
        print("[google_oauth_routes] oauth_state_repo ->", oauth_state_repo)
        return GoogleOAuthService(db=db, oauth_state_repo=oauth_state_repo)
    except Exception as e:
        print("[google_oauth_routes] error ->", e)
        raise e

@router.get(
    "/login",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Start Google OAuth login (server-controlled)",
)
async def google_oauth_login(
    request: Request,
    redirect_url: str | None = Query(
        default=None,
        description="Optional frontend callback URL (defaults to FRONTEND_URL/login)",
    ),
    fcm_token: str | None = Query(default=None, description="Optional FCM token"),
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
):
    """
    Frontend redirects the browser here to start Google OAuth.
    After Google login, user is redirected to the frontend with JWT tokens in query params.
    """
    try:
        return await oauth_service.initiate_login(
            request=request,
            redirect_url=redirect_url,
            fcm_token=fcm_token,
        )
    except GoogleRedirectNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/callback/",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Google OAuth callback (trailing slash — matches Google redirect URI)",
)
async def google_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
):
    """
    Google redirects here. Backend redirects to the frontend /login URL with JWT tokens in query params.
    """
    return await oauth_service.handle_callback(
        code=code,
        state=state,
        error=error,
        request=request,
    )
