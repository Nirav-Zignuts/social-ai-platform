import uuid
from datetime import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import GeneratedPostStatus, NotificationChannel, NotificationType
from app.models.generated_post import GeneratedPost
from app.models.notification import Notification
from app.models.user import User
from app.models.workspace import Workspace
from app.services.generation.graph import get_compiled_graph
from langgraph.checkpoint.memory import MemorySaver


class MockStructuredLLM:
    def __init__(self, return_value):
        self.return_value = return_value

    def invoke(self, *args, **kwargs):
        if isinstance(self.return_value, Exception):
            raise self.return_value
        return self.return_value


class MockModel:
    def __init__(self, return_value):
        self.return_value = return_value

    def with_structured_output(self, schema):
        return MockStructuredLLM(self.return_value)


def _llm_side_effect():
    def side_effect(purpose):
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="educational", rationale="Test"))
        if purpose == "writer":
            return MockModel(
                MagicMock(
                    caption="Test Cap",
                    hashtags=["#t"],
                    cta="Click",
                    needs_image=False,
                )
            )
        if purpose == "reviewer":
            return MockModel(MagicMock(score=95, notes="Great"))
        return MockModel(MagicMock())

    return side_effect


@pytest.mark.asyncio
@patch("app.services.generation.nodes.notify_post_auto_approved")
@patch("app.services.generation.nodes.notify_post_ready_for_review")
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.retrieve_context")
async def test_require_human_approval_branches(
    mock_retrieve,
    mock_get_model,
    mock_notify_ready,
    mock_notify_auto,
    db,
):
    mock_retrieve.return_value = []
    mock_get_model.side_effect = _llm_side_effect()

    user = User(email=f"{uuid.uuid4()}@test.com", full_name="Owner")
    db.add(user)
    db.commit()

    ws_review = Workspace(
        name="Review WS",
        slug=f"review-{uuid.uuid4()}",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(12, 0),
        require_human_approval=True,
    )
    ws_auto = Workspace(
        name="Auto WS",
        slug=f"auto-{uuid.uuid4()}",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(12, 0),
        require_human_approval=False,
    )
    db.add_all([ws_review, ws_auto])
    db.commit()

    checkpointer = MemorySaver()
    graph = get_compiled_graph(checkpointer=checkpointer)

    cycle_review = str(uuid.uuid4())
    cycle_auto = str(uuid.uuid4())

    await graph.ainvoke(
        {
            "workspace_id": str(ws_review.id),
            "generation_cycle_id": cycle_review,
            "calendar_date": "2026-01-01",
        },
        config={"configurable": {"thread_id": cycle_review}},
    )

    post_review = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.generation_cycle_id == cycle_review)
        .first()
    )
    assert post_review.status == GeneratedPostStatus.PENDING_REVIEW.value
    assert post_review.scheduled_for is None
    mock_notify_ready.assert_called_once_with(str(post_review.id))
    mock_notify_auto.assert_not_called()

    await graph.ainvoke(
        {
            "workspace_id": str(ws_auto.id),
            "generation_cycle_id": cycle_auto,
            "calendar_date": "2026-01-01",
        },
        config={"configurable": {"thread_id": cycle_auto}},
    )

    post_auto = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.generation_cycle_id == cycle_auto)
        .first()
    )

    assert post_auto.status == GeneratedPostStatus.APPROVED.value
    assert post_auto.scheduled_for is not None
    mock_notify_auto.assert_called_once_with(str(post_auto.id))

    pending_for_auto = (
        db.query(GeneratedPost)
        .filter(
            GeneratedPost.workspace_id == ws_auto.id,
            GeneratedPost.status == GeneratedPostStatus.PENDING_REVIEW.value,
        )
        .count()
    )
    assert pending_for_auto == 0
