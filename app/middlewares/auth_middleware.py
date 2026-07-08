
from typing import Any
from urllib import request

from fastapi import HTTPException, Request,status
import jwt

from app.common.messages import ErrorMessages
from app.db.session import SessionLocal
from app.models.user_session import UserSession
from app.security.token import TokenManager

token_manager = TokenManager()

def get_token_from_header(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN,
        )
    return auth_header.removeprefix("Bearer ").strip()

def verify_access_token(token: str):
    try:
        payload = token_manager.decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_EXPIRED,
        )

    if not payload or payload.get("_expired"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_EXPIRED,
        )

    user_id = payload.get("sub")
    return user_id

def _session_exists_for_token(db, token: str) -> bool:
    """Return True if a UserSession record exists with this access_token."""
    return (
        db.query(UserSession.id).filter(UserSession.access_token == token).first()
        is not None
    )


def require_auth(request: Request) -> dict[str, Any]:
    
    try:
        token = get_token_from_header(request)
        user_id = verify_access_token(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_TOKEN,
            )
        db = SessionLocal()
        if not _session_exists_for_token(db, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.SESSION_NOT_FOUND,
            )
        return {"user_id": user_id}
    except HTTPException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN,
        )