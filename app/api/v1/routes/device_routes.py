from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.notification_schema import (
    DeviceRegisterRequest,
    DeviceUnregisterRequest,
)
from app.common.messages import AuthMessages, ErrorMessage, ErrorMessages, SuccessMessage
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.services.device_token_service import DeviceTokenService

router = APIRouter(prefix="/devices", tags=["Devices"])


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.post("/register", response_model=SuccessMessage | ErrorMessage)
async def register_device(
    payload: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        data = DeviceTokenService(db).register(
            _user_id(current_user),
            fcm_token=payload.fcm_token,
            platform=payload.platform,
            device_id=payload.device_id,
            app_version=payload.app_version,
        )
        return SuccessMessage(
            message=AuthMessages.DEVICE_REGISTERED,
            data=data,
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )


@router.delete("", response_model=SuccessMessage | ErrorMessage)
@router.post("/unregister", response_model=SuccessMessage | ErrorMessage)
async def unregister_device(
    payload: DeviceUnregisterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        DeviceTokenService(db).unregister(
            _user_id(current_user),
            fcm_token=payload.fcm_token,
        )
        return SuccessMessage(
            message=AuthMessages.DEVICE_UNREGISTERED,
            code=status.HTTP_200_OK,
        )
    except HTTPException as e:
        return ErrorMessage(message=e.detail, code=e.status_code)
    except Exception as e:
        return ErrorMessage(
            message=ErrorMessages.SERVER_ERROR,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=str(e),
        )
