from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.schemas.onboarding_chat_schema import (
    OnboardingChatMessageRequest,
    OnboardingChatSessionResponse,
    OnboardingChatStartResponse,
    OnboardingChatTurnResponse,
)
from app.common.messages import ErrorMessage, ErrorMessages, SuccessMessage
from app.db.session import get_db
from app.middlewares.auth_middleware import require_auth
from app.onboarding_chat.quick_replies import normalize_stored_quick_replies
from app.onboarding_chat.schemas import BusinessProfileDraft
from app.services.onboarding_chat_service import OnboardingChatService

router = APIRouter(prefix="/workspaces", tags=["Onboarding Chat"])


def _user_id(current_user) -> UUID:
    user_id_str = current_user.get("user_id")
    return UUID(user_id_str) if isinstance(user_id_str, str) else user_id_str


@router.post(
    "/{workspace_id}/onboarding-chat/start",
    response_model=SuccessMessage,
    summary="Start onboarding chat session",
)
async def start_onboarding_chat(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        result = OnboardingChatService(db).start_session(
            workspace_id, _user_id(current_user)
        )
        payload = OnboardingChatStartResponse.model_validate(result)
        return SuccessMessage(
            message="Onboarding chat started",
            data=payload.model_dump(mode="json"),
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


@router.post(
    "/{workspace_id}/onboarding-chat/{session_id}/message",
    response_model=SuccessMessage,
    summary="Send onboarding chat user message",
)
async def send_onboarding_chat_message(
    workspace_id: UUID,
    session_id: UUID,
    payload: OnboardingChatMessageRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        result = OnboardingChatService(db).send_message(
            workspace_id,
            session_id,
            _user_id(current_user),
            content=payload.content,
            selected_replies=payload.selected_replies,
        )
        profile = result.get("synthesized_profile")
        response = OnboardingChatTurnResponse(
            message=result["message"],
            quick_replies=result.get("quick_replies") or [],
            allow_multiple=bool(result.get("allow_multiple")),
            is_complete=bool(result.get("is_complete")),
            synthesized_profile=(
                BusinessProfileDraft.model_validate(profile)
                if profile is not None
                else None
            ),
            turn_count=result.get("turn_count") or 0,
            collected_fields=result.get("collected_fields") or {},
            forced_synthesis=bool(result.get("forced_synthesis")),
        )
        return SuccessMessage(
            message=(
                "Onboarding profile synthesized"
                if response.is_complete
                else "Onboarding chat reply generated"
            ),
            data=response.model_dump(mode="json"),
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


@router.get(
    "/{workspace_id}/onboarding-chat/{session_id}",
    response_model=SuccessMessage,
    summary="Get onboarding chat session + transcript",
)
async def get_onboarding_chat_session(
    workspace_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    try:
        result = OnboardingChatService(db).get_session(
            workspace_id, session_id, _user_id(current_user)
        )
        messages = []
        for m in result["messages"]:
            options, allow_multiple = normalize_stored_quick_replies(m.quick_replies)
            messages.append(
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "quick_replies": options or None,
                    "allow_multiple": allow_multiple if m.role == "assistant" else False,
                    "created_at": m.created_at,
                }
            )
        payload = OnboardingChatSessionResponse.model_validate(
            {
                **result,
                "messages": messages,
            }
        )
        return SuccessMessage(
            message="Onboarding chat session retrieved",
            data=payload.model_dump(mode="json"),
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
