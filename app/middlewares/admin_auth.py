from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.common.messages import AdminErrorMessages
from app.db.session import get_db
from app.models.admin import Admin
from app.repositories.admin_auth import AdminAuthRepository
from app.services.admin_auth_service import decrypt_admin_token

ADMIN_AUTH_HEADER = "X-Admin-Authorization"


def _not_found() -> HTTPException:
    # Deliberately hide whether the secret admin route exists.
    return HTTPException(status_code=404, detail=AdminErrorMessages.NOT_FOUND)


def require_admin_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> Admin:
    try:
        header = (request.headers.get(ADMIN_AUTH_HEADER) or "").strip()
        if not header.startswith("Bearer "):
            raise _not_found()
        token = header.removeprefix("Bearer ").strip()
        if not token:
            raise _not_found()

        payload = decrypt_admin_token(token)
        admin = AdminAuthRepository(db).get_active_by_email(
            str(payload["email"]).strip().lower()
        )
        if not admin or admin.id != UUID(str(payload["admin_id"])):
            raise _not_found()
        return admin
    except HTTPException:
        raise
    except Exception:
        raise _not_found()
