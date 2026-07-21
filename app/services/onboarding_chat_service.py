from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.analytics.ai_usage_logger import invoke_structured_with_usage
from app.common.messages import ErrorMessages
from app.core.llm_client import get_chat_model
from app.models.onboarding_chat_message import OnboardingChatMessage
from app.models.onboarding_chat_session import OnboardingChatSession
from app.onboarding_chat.constants import (
    ALL_PROFILE_FIELD_KEYS,
    MAX_ONBOARDING_TURNS,
)
from app.onboarding_chat.prompts import (
    FOLLOW_UP_USER_PROMPT,
    OPENING_USER_PROMPT,
    SYNTHESIS_USER_PROMPT,
    build_synthesis_system_prompt,
    build_turn_system_prompt,
)
from app.onboarding_chat.quick_replies import (
    default_allow_multiple,
    encode_quick_replies,
    fallback_quick_replies,
    normalize_stored_quick_replies,
)
from app.onboarding_chat.schemas import BusinessProfileDraft, OnboardingChatTurn
from app.repositories.onboarding_chat import (
    OnboardingChatMessageRepository,
    OnboardingChatSessionRepository,
)
from app.repositories.workspace import WorkspaceRepository

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _merge_collected_fields(
    existing: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        if key not in ALL_PROFILE_FIELD_KEYS:
            continue
        if value is None:
            continue
        merged[key] = value
    return merged


def _transcript_dicts(messages: list[OnboardingChatMessage]) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]


def build_user_content(
    content: str | None,
    selected_replies: list[str] | None,
) -> str:
    """Merge free text + multi-selected chips into one transcript user message."""
    replies = [r.strip() for r in (selected_replies or []) if r and str(r).strip()]
    text = (content or "").strip()
    parts: list[str] = []
    if replies:
        parts.append("Selected options: " + "; ".join(replies))
    if text:
        parts.append(text)
    return "\n".join(parts).strip()


def ensure_turn_quick_replies(
    turn: OnboardingChatTurn,
    collected_fields: dict[str, Any] | None,
) -> OnboardingChatTurn:
    """Guarantee chips on question turns; clear chips on completion wrap-up."""
    if turn.is_complete:
        turn.quick_replies = []
        turn.allow_multiple = False
        return turn

    options = [o.strip() for o in (turn.quick_replies or []) if o and str(o).strip()]
    if len(options) < 2:
        options = fallback_quick_replies(collected_fields)
    # Cap at 5 for FE chip rows
    turn.quick_replies = options[:5]
    if turn.allow_multiple is None:
        turn.allow_multiple = default_allow_multiple(collected_fields)
    return turn


def synthesize_business_profile(
    db: Session,
    session_id: str | UUID,
) -> BusinessProfileDraft:
    """
    Final structured profile generation from transcript + collected_fields.
    Does NOT persist to business_profiles — returns a draft for FE review.
    """
    session_repo = OnboardingChatSessionRepository(db)
    message_repo = OnboardingChatMessageRepository(db)

    session_uuid = UUID(str(session_id))
    session = session_repo.get_by_id(session_uuid)
    if not session or session.is_deleted:
        raise HTTPException(status_code=404, detail="Onboarding chat session not found")

    messages = message_repo.list_for_session(session.id)
    system = build_synthesis_system_prompt(
        session.collected_fields or {},
        _transcript_dicts(messages),
    )
    model = get_chat_model("onboarding_synthesizer")
    draft: BusinessProfileDraft = invoke_structured_with_usage(
        model=model,
        schema=BusinessProfileDraft,
        prompt=[
            SystemMessage(content=system),
            HumanMessage(content=SYNTHESIS_USER_PROMPT),
        ],
        workspace_id=session.workspace_id,
        generated_post_id=None,
        agent_purpose="onboarding_synthesizer",
    )
    return draft


class OnboardingChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspace_repo = WorkspaceRepository(db)
        self.session_repo = OnboardingChatSessionRepository(db)
        self.message_repo = OnboardingChatMessageRepository(db)

    def _get_owned_workspace(self, workspace_id: UUID, user_id: UUID):
        workspace = self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=404, detail=ErrorMessages.WORKSPACE_NOT_FOUND
            )
        if workspace.owner_id != user_id:
            raise HTTPException(status_code=403, detail=ErrorMessages.FORBIDDEN)
        return workspace

    def _get_session_or_404(
        self, workspace_id: UUID, session_id: UUID
    ) -> OnboardingChatSession:
        session = self.session_repo.get_for_workspace(session_id, workspace_id)
        if not session:
            raise HTTPException(
                status_code=404, detail="Onboarding chat session not found"
            )
        return session

    def _invoke_turn(
        self,
        *,
        collected_fields: dict[str, Any],
        transcript: list[dict[str, str]],
        is_opening: bool,
        workspace_id: UUID,
    ) -> OnboardingChatTurn:
        system = build_turn_system_prompt(collected_fields, transcript)
        user_prompt = OPENING_USER_PROMPT if is_opening else FOLLOW_UP_USER_PROMPT
        model = get_chat_model("onboarding_assistant")
        turn = invoke_structured_with_usage(
            model=model,
            schema=OnboardingChatTurn,
            prompt=[
                SystemMessage(content=system),
                HumanMessage(content=user_prompt),
            ],
            workspace_id=workspace_id,
            generated_post_id=None,
            agent_purpose="onboarding_assistant",
        )
        return ensure_turn_quick_replies(turn, collected_fields)

    def _persist_assistant_message(
        self,
        session: OnboardingChatSession,
        turn: OnboardingChatTurn,
    ) -> OnboardingChatMessage:
        options = list(turn.quick_replies or [])
        payload = (
            encode_quick_replies(options, bool(turn.allow_multiple))
            if options
            else None
        )
        msg = OnboardingChatMessage(
            session_id=session.id,
            role="assistant",
            content=turn.message,
            quick_replies=payload,
        )
        return self.message_repo.create(msg)

    def start_session(self, workspace_id: UUID, user_id: UUID) -> dict:
        self._get_owned_workspace(workspace_id, user_id)

        session = OnboardingChatSession(
            workspace_id=workspace_id,
            status="active",
            collected_fields={},
            turn_count=0,
            started_at=_utcnow(),
        )
        session = self.session_repo.create(session)

        turn = self._invoke_turn(
            collected_fields={},
            transcript=[],
            is_opening=True,
            workspace_id=workspace_id,
        )
        # Opening turn must not invent extracted fields / completion.
        turn.extracted_updates = {}
        turn.is_complete = False
        turn = ensure_turn_quick_replies(turn, {})

        self._persist_assistant_message(session, turn)

        return {
            "session_id": session.id,
            "message": turn.message,
            "quick_replies": list(turn.quick_replies or []),
            "allow_multiple": bool(turn.allow_multiple),
        }

    def send_message(
        self,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
        content: str | None = None,
        selected_replies: list[str] | None = None,
    ) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        session = self._get_session_or_404(workspace_id, session_id)

        if session.status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Onboarding chat session is {session.status}, not active",
            )

        effective = build_user_content(content, selected_replies)
        if not effective:
            raise HTTPException(
                status_code=400,
                detail="Provide content and/or selected_replies",
            )

        user_msg = OnboardingChatMessage(
            session_id=session.id,
            role="user",
            content=effective,
            quick_replies=None,
        )
        self.message_repo.create(user_msg)

        session.turn_count = int(session.turn_count or 0) + 1
        forced_synthesis = session.turn_count > MAX_ONBOARDING_TURNS

        if forced_synthesis:
            logger.warning(
                "Onboarding chat turn cap reached (session=%s workspace=%s turns=%s) — "
                "forcing synthesis without another conversational LLM turn",
                session.id,
                workspace_id,
                session.turn_count,
            )
            session.status = "completed"
            session.completed_at = _utcnow()
            self.session_repo.update(session)

            draft = synthesize_business_profile(self.db, session.id)
            wrap_up = (
                "We've covered a lot — I'll put together your business profile "
                "from what you've shared so far. You can tweak anything that looks off."
            )
            assistant = OnboardingChatMessage(
                session_id=session.id,
                role="assistant",
                content=wrap_up,
                quick_replies=None,
            )
            self.message_repo.create(assistant)

            return {
                "message": wrap_up,
                "quick_replies": [],
                "allow_multiple": False,
                "is_complete": True,
                "synthesized_profile": draft,
                "turn_count": session.turn_count,
                "collected_fields": session.collected_fields or {},
                "forced_synthesis": True,
            }

        prior = self.message_repo.list_for_session(session.id)
        turn = self._invoke_turn(
            collected_fields=session.collected_fields or {},
            transcript=_transcript_dicts(prior),
            is_opening=False,
            workspace_id=workspace_id,
        )

        session.collected_fields = _merge_collected_fields(
            session.collected_fields,
            turn.extracted_updates,
        )

        synthesized_profile = None
        if turn.is_complete:
            session.status = "completed"
            session.completed_at = _utcnow()
            turn.quick_replies = []
            turn.allow_multiple = False

        self.session_repo.update(session)
        self._persist_assistant_message(session, turn)

        if turn.is_complete:
            synthesized_profile = synthesize_business_profile(self.db, session.id)

        return {
            "message": turn.message,
            "quick_replies": list(turn.quick_replies or []),
            "allow_multiple": bool(turn.allow_multiple),
            "is_complete": bool(turn.is_complete),
            "synthesized_profile": synthesized_profile,
            "turn_count": session.turn_count,
            "collected_fields": session.collected_fields or {},
            "forced_synthesis": False,
        }

    def get_session(
        self,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> dict:
        self._get_owned_workspace(workspace_id, user_id)
        session = self._get_session_or_404(workspace_id, session_id)
        messages = self.message_repo.list_for_session(session.id)
        return {
            "session_id": session.id,
            "workspace_id": session.workspace_id,
            "status": session.status,
            "collected_fields": session.collected_fields or {},
            "turn_count": session.turn_count,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "messages": messages,
        }
