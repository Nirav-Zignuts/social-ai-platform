"""Tests for onboarding chat (mocked Gemini / structured turns)."""

from unittest.mock import patch

import pytest

from app.onboarding_chat.schemas import BusinessProfileDraft, OnboardingChatTurn
from app.services.onboarding_chat_service import (
    OnboardingChatService,
    build_user_content,
    ensure_turn_quick_replies,
)


class _StructuredStub:
    def __init__(self, value):
        self.value = value

    def invoke(self, _messages):
        return self.value


class _ModelStub:
    def __init__(self, value):
        self.value = value

    def with_structured_output(self, _schema):
        return _StructuredStub(self.value)


@pytest.fixture
def opening_turn():
    return OnboardingChatTurn(
        message="Hey! What's your business called?",
        quick_replies=[],
        allow_multiple=False,
        extracted_updates={},
        is_complete=False,
    )


@pytest.fixture
def follow_up_turn():
    return OnboardingChatTurn(
        message="Nice — what industry are you in?",
        quick_replies=["Retail", "Food & Drink", "Services", "Health & Wellness"],
        allow_multiple=False,
        extracted_updates={"business_name": "Leafling Urban Nursery"},
        is_complete=False,
    )


def test_build_user_content_supports_multi_select():
    text = build_user_content(
        "also cute vibes",
        ["Warm and friendly", "Bold and fun"],
    )
    assert "Warm and friendly" in text
    assert "Bold and fun" in text
    assert "also cute vibes" in text


def test_ensure_turn_quick_replies_fills_empty_chips():
    turn = OnboardingChatTurn(
        message="What industry?",
        quick_replies=[],
        allow_multiple=False,
        extracted_updates={},
        is_complete=False,
    )
    fixed = ensure_turn_quick_replies(turn, {"business_name": "X"})
    assert len(fixed.quick_replies) >= 3


@patch("app.services.onboarding_chat_service.get_chat_model")
def test_start_session_always_returns_quick_replies(
    mock_get_model, db, workspace, user, opening_turn
):
    mock_get_model.return_value = _ModelStub(opening_turn)
    service = OnboardingChatService(db)
    result = service.start_session(workspace.id, user.id)

    assert result["message"] == opening_turn.message
    assert len(result["quick_replies"]) >= 3
    assert "allow_multiple" in result
    session_id = result["session_id"]

    detail = service.get_session(workspace.id, session_id, user.id)
    assert detail["status"] == "active"
    assert detail["turn_count"] == 0
    assert len(detail["messages"]) == 1
    assert detail["messages"][0].role == "assistant"


@patch("app.services.onboarding_chat_service.synthesize_business_profile")
@patch("app.services.onboarding_chat_service.get_chat_model")
def test_send_message_merges_extracted_fields(
    mock_get_model,
    mock_synthesize,
    db,
    workspace,
    user,
    opening_turn,
    follow_up_turn,
):
    mock_get_model.side_effect = [
        _ModelStub(opening_turn),
        _ModelStub(follow_up_turn),
    ]
    service = OnboardingChatService(db)
    started = service.start_session(workspace.id, user.id)

    reply = service.send_message(
        workspace.id,
        started["session_id"],
        user.id,
        content="It's called Leafling Urban Nursery",
    )
    assert reply["is_complete"] is False
    assert reply["collected_fields"]["business_name"] == "Leafling Urban Nursery"
    assert reply["quick_replies"] == follow_up_turn.quick_replies
    assert reply["turn_count"] == 1
    mock_synthesize.assert_not_called()


@patch("app.services.onboarding_chat_service.synthesize_business_profile")
@patch("app.services.onboarding_chat_service.get_chat_model")
def test_send_message_accepts_selected_replies(
    mock_get_model,
    mock_synthesize,
    db,
    workspace,
    user,
    opening_turn,
    follow_up_turn,
):
    mock_get_model.side_effect = [
        _ModelStub(opening_turn),
        _ModelStub(follow_up_turn),
    ]
    service = OnboardingChatService(db)
    started = service.start_session(workspace.id, user.id)

    reply = service.send_message(
        workspace.id,
        started["session_id"],
        user.id,
        selected_replies=["It's a shop / store", "It's a cafe / restaurant"],
    )
    assert reply["turn_count"] == 1
    detail = service.get_session(workspace.id, started["session_id"], user.id)
    user_msgs = [m for m in detail["messages"] if m.role == "user"]
    assert len(user_msgs) == 1
    assert "It's a shop / store" in user_msgs[0].content
    assert "It's a cafe / restaurant" in user_msgs[0].content


@patch("app.services.onboarding_chat_service.synthesize_business_profile")
@patch("app.services.onboarding_chat_service.get_chat_model")
def test_complete_turn_triggers_synthesis(
    mock_get_model,
    mock_synthesize,
    db,
    workspace,
    user,
    opening_turn,
):
    complete = OnboardingChatTurn(
        message="That's everything — putting your profile together!",
        quick_replies=["ignore"],
        allow_multiple=True,
        extracted_updates={"brand_voice": "Warm and reassuring"},
        is_complete=True,
    )
    draft = BusinessProfileDraft(
        business_name="Leafling",
        industry="Retail",
        description="A plant shop.",
        target_audience="Urban plant parents",
        brand_voice="Warm and reassuring friend who loves plants.",
        prohibited_words=[],
        required_keywords=["Leafling"],
        synthesis_notes=None,
    )
    mock_get_model.side_effect = [_ModelStub(opening_turn), _ModelStub(complete)]
    mock_synthesize.return_value = draft

    service = OnboardingChatService(db)
    started = service.start_session(workspace.id, user.id)
    reply = service.send_message(
        workspace.id,
        started["session_id"],
        user.id,
        content="Warm and friendly",
    )

    assert reply["is_complete"] is True
    assert reply["quick_replies"] == []
    assert reply["allow_multiple"] is False
    assert reply["synthesized_profile"].business_name == "Leafling"
    mock_synthesize.assert_called_once()

    detail = service.get_session(workspace.id, started["session_id"], user.id)
    assert detail["status"] == "completed"


@patch("app.services.onboarding_chat_service.synthesize_business_profile")
@patch("app.services.onboarding_chat_service.get_chat_model")
def test_turn_cap_forces_synthesis_without_llm_turn(
    mock_get_model,
    mock_synthesize,
    db,
    workspace,
    user,
    opening_turn,
):
    mock_get_model.return_value = _ModelStub(opening_turn)
    mock_synthesize.return_value = BusinessProfileDraft(
        business_name="Cap Co",
        industry="Services",
        description="Forced draft",
        target_audience="Locals",
        brand_voice="Friendly",
        synthesis_notes="Incomplete due to turn cap",
    )
    service = OnboardingChatService(db)
    started = service.start_session(workspace.id, user.id)
    session_id = started["session_id"]

    session = service.session_repo.get_by_id(session_id)
    session.turn_count = 20
    service.session_repo.update(session)

    reply = service.send_message(workspace.id, session_id, user.id, content="whatever")
    assert reply["forced_synthesis"] is True
    assert reply["is_complete"] is True
    assert reply["synthesized_profile"].business_name == "Cap Co"
    assert mock_get_model.call_count == 1
