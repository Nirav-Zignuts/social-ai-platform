import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import GeneratedPostStatus
from app.models.generated_post import GeneratedPost
from app.services.generation.graph import get_compiled_graph
from app.services.generation.resume import _resume_graph_for_regenerate_async
from langgraph.checkpoint.memory import MemorySaver


class MockStructuredLLM:
    def __init__(self, return_value):
        self.return_value = return_value

    def invoke(self, *args, **kwargs):
        return self.return_value


class MockModel:
    def __init__(self, return_value):
        self.return_value = return_value

    def with_structured_output(self, schema):
        return MockStructuredLLM(self.return_value)


@pytest.mark.asyncio
@patch("app.services.generation.nodes.notify_post_ready_for_review")
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.retrieve_context")
async def test_regenerate_resume_updates_same_post(
    mock_retrieve,
    mock_get_model,
    mock_notify,
    db,
    workspace,
):
    mock_retrieve.return_value = []
    call_count = {"n": 0}

    def side_effect(purpose):
        call_count["n"] += 1
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="educational", rationale="Test"))
        if purpose == "writer":
            return MockModel(
                MagicMock(
                    caption=f"Caption v{call_count['n']}",
                    hashtags=["#t"],
                    cta="Click",
                    needs_image=False,
                )
            )
        if purpose == "reviewer":
            return MockModel(MagicMock(score=95, notes="Great"))
        return MockModel(MagicMock())

    mock_get_model.side_effect = side_effect

    checkpointer = MemorySaver()
    graph = get_compiled_graph(checkpointer=checkpointer)
    cycle_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cycle_id}}

    await graph.ainvoke(
        {
            "workspace_id": str(workspace.id),
            "generation_cycle_id": cycle_id,
            "calendar_date": "2026-01-01",
        },
        config=config,
    )

    original = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.generation_cycle_id == cycle_id)
        .one()
    )
    original_id = original.id

    await _resume_graph_for_regenerate_async(
        cycle_id,
        "Make it punchier",
        checkpointer=checkpointer,
    )

    db.expire_all()
    updated = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.generation_cycle_id == cycle_id)
        .one()
    )
    assert updated.id == original_id
    assert updated.regenerate_count == 1
    assert updated.status == GeneratedPostStatus.PENDING_REVIEW.value
    assert mock_notify.call_count == 2
