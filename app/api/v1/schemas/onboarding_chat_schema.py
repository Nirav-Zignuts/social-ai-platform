from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.onboarding_chat.schemas import BusinessProfileDraft


class OnboardingChatMessageRequest(BaseModel):
    """User can send free text, one/many chip selections, or both."""

    content: Optional[str] = Field(default=None, max_length=4000)
    selected_replies: list[str] = Field(
        default_factory=list,
        description="One or more tapped quick_reply chips (multi-select supported).",
    )

    @model_validator(mode="after")
    def _require_payload(self) -> "OnboardingChatMessageRequest":
        text = (self.content or "").strip()
        replies = [r.strip() for r in self.selected_replies if r and str(r).strip()]
        object.__setattr__(self, "content", text or None)
        object.__setattr__(self, "selected_replies", replies)
        if not text and not replies:
            raise ValueError("Provide content and/or selected_replies")
        return self


class OnboardingChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    quick_replies: Optional[list[str]] = None
    allow_multiple: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingChatStartResponse(BaseModel):
    session_id: UUID
    message: str
    quick_replies: list[str] = Field(default_factory=list)
    allow_multiple: bool = False


class OnboardingChatTurnResponse(BaseModel):
    message: str
    quick_replies: list[str] = Field(default_factory=list)
    allow_multiple: bool = False
    is_complete: bool = False
    synthesized_profile: Optional[BusinessProfileDraft] = None
    turn_count: int = 0
    collected_fields: dict[str, Any] = Field(default_factory=dict)
    forced_synthesis: bool = False


class OnboardingChatSessionResponse(BaseModel):
    session_id: UUID
    workspace_id: UUID
    status: str
    collected_fields: dict[str, Any]
    turn_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    messages: list[OnboardingChatMessageResponse]
