import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import GeneratedPostStatus
from app.models.generated_post import GeneratedPost
from app.services.generation.graph import get_compiled_graph
from app.services.generation.nodes import image_node
from app.services.generation.resume import (
    RegenerationCheckpointError,
    _resume_graph_for_regenerate_async,
)
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


@patch("app.services.generation.nodes.generate_image", return_value=None)
@patch("app.services.generation.nodes.get_chat_model")
def test_failed_forced_image_regeneration_preserves_previous_image(
    mock_get_model,
    mock_generate_image,
):
    mock_get_model.return_value = MockModel(MagicMock(visual_prompt="A clean scene"))
    state = {
        "workspace_id": str(uuid.uuid4()),
        "generation_cycle_id": str(uuid.uuid4()),
        "caption": "Updated caption",
        "content_type": "educational",
        "business_context": "Sustainable clothing",
        "ai_config": {},
        "needs_image": False,
        "force_regenerate_image": True,
        "image_url": "https://example.com/original.jpg",
    }

    result = image_node(state)

    mock_generate_image.assert_called_once()
    assert result["image_url"] == "https://example.com/original.jpg"
    assert result["force_regenerate_image"] is False


@pytest.mark.asyncio
async def test_regenerate_without_checkpoint_fails_explicitly():
    with pytest.raises(RegenerationCheckpointError):
        await _resume_graph_for_regenerate_async(
            str(uuid.uuid4()),
            "Rewrite this",
            checkpointer=MemorySaver(),
        )


@pytest.mark.asyncio
@patch("app.services.generation.nodes.generate_image")
@patch("app.services.generation.nodes.notify_post_regenerated")
@patch("app.services.generation.nodes.notify_post_ready_for_review")
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.retrieve_context")
async def test_regenerate_resume_updates_same_post(
    mock_retrieve,
    mock_get_model,
    mock_notify_ready,
    mock_notify_regenerated,
    mock_generate_image,
    db,
    workspace,
):
    mock_retrieve.return_value = []
    mock_generate_image.return_value = "https://example.com/regenerated.jpg"
    call_count = {"n": 0}

    def side_effect(purpose):
        call_count["n"] += 1
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="educational", rationale="Test"))
        if purpose == "writer":
            return MockModel(
                MagicMock(
                    caption=f"Caption v{call_count['n']}",
                    hashtags=[f"#version{call_count['n']}"],
                    cta=f"Click v{call_count['n']}",
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
    original_caption = original.caption
    original_hashtags = original.hashtags
    original_cta = original.cta

    await _resume_graph_for_regenerate_async(
        cycle_id,
        "Make it punchier",
        regenerate_image=True,
        checkpointer=checkpointer,
    )

    db.expire_all()
    updated = (
        db.query(GeneratedPost)
        .filter(GeneratedPost.generation_cycle_id == cycle_id)
        .one()
    )
    assert updated.id == original_id
    assert updated.caption != original_caption
    assert updated.hashtags != original_hashtags
    assert updated.cta != original_cta
    assert updated.image_url == "https://example.com/regenerated.jpg"
    assert updated.regenerate_count == 1
    assert updated.status == GeneratedPostStatus.PENDING_REVIEW.value
    mock_notify_ready.assert_called_once_with(str(original_id))
    mock_notify_regenerated.assert_called_once_with(str(original_id))
    mock_generate_image.assert_called_once()
