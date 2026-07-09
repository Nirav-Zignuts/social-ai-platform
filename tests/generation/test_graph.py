import pytest
import pytest_asyncio
import os
import uuid
import asyncio
from unittest.mock import patch, MagicMock
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.models import * # Import all models to resolve mapper errors
from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace
from app.models.generated_post import GeneratedPost
from sqlalchemy.orm import configure_mappers

configure_mappers()

from app.core.config import settings
from app.services.generation.graph import get_compiled_graph
from app.core.llm_client import get_chat_model

# Helper to mock structured LLM output
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

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def workspace(db):
    user = User(email=f"{uuid.uuid4()}@test.com", full_name="Test User")
    db.add(user)
    db.commit()
    
    ws = Workspace(
        name="Test WS", 
        slug=f"test-ws-{uuid.uuid4()}", 
        owner_id=user.id,
        timezone="UTC", 
        preferred_post_time="12:00:00"
    )
    db.add(ws)
    db.commit()
    return ws

from langgraph.checkpoint.memory import MemorySaver

@pytest.fixture
def checkpointer():
    return MemorySaver()

@pytest.mark.asyncio
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.generate_image")
@patch("app.services.generation.nodes.retrieve_context")
async def test_full_happy_path_needs_image(mock_retrieve, mock_gen_image, mock_get_model, workspace, checkpointer):
    mock_retrieve.return_value = []
    mock_gen_image.return_value = "storage/test_img.jpeg"
    
    # Mock LLM outputs
    def side_effect(purpose):
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="educational", rationale="Test"))
        elif purpose == "writer":
            return MockModel(MagicMock(caption="Test Cap", hashtags=["#t"], cta="Click", needs_image=True))
        elif purpose == "reviewer":
            return MockModel(MagicMock(score=95, notes="Great"))
            
    mock_get_model.side_effect = side_effect
    
    graph = get_compiled_graph(checkpointer=checkpointer)
    cycle_id = str(uuid.uuid4())
    
    state = {
        "workspace_id": str(workspace.id),
        "generation_cycle_id": cycle_id,
        "calendar_date": "2026-01-01",
    }
    
    config = {"configurable": {"thread_id": cycle_id}}
    result = await graph.ainvoke(state, config=config)
    
    assert result["needs_image"] is True
    assert result["image_url"] == "storage/test_img.jpeg"
    assert result["reviewer_passed"] is True
    assert result["reviewer_score"] == 95
    assert result["post_id"] is not None
    mock_gen_image.assert_called_once()
    


@pytest.mark.asyncio
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.generate_image")
@patch("app.services.generation.nodes.retrieve_context")
async def test_full_happy_path_no_image(mock_retrieve, mock_gen_image, mock_get_model, workspace, checkpointer):
    mock_retrieve.return_value = []
    def side_effect(purpose):
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="faq", rationale="Test"))
        elif purpose == "writer":
            return MockModel(MagicMock(caption="Test", hashtags=[], cta="", needs_image=False))
        elif purpose == "reviewer":
            return MockModel(MagicMock(score=100, notes=""))
            
    mock_get_model.side_effect = side_effect
    
    graph = get_compiled_graph(checkpointer=checkpointer)
    cycle_id = str(uuid.uuid4())
    
    state = {
        "workspace_id": str(workspace.id),
        "generation_cycle_id": cycle_id,
        "calendar_date": "2026-01-01",
    }
    
    config = {"configurable": {"thread_id": cycle_id}}
    result = await graph.ainvoke(state, config=config)
    
    assert result.get("needs_image") is False
    assert result.get("image_url") is None
    mock_gen_image.assert_not_called()

@pytest.mark.asyncio
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.retrieve_context")
async def test_retry_cap_logic(mock_retrieve, mock_get_model, workspace, checkpointer):
    mock_retrieve.return_value = []
    # Reviewer always fails (score 50)
    def side_effect(purpose):
        if purpose == "strategist":
            return MockModel(MagicMock(content_type="promotional", rationale="Test"))
        elif purpose == "writer":
            return MockModel(MagicMock(caption="Test", hashtags=[], cta="", needs_image=False))
        elif purpose == "reviewer":
            return MockModel(MagicMock(score=50, notes="Fail"))
            
    mock_get_model.side_effect = side_effect
    
    graph = get_compiled_graph(checkpointer=checkpointer)
    cycle_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cycle_id}}
    
    state = {
        "workspace_id": str(workspace.id),
        "generation_cycle_id": cycle_id,
        "calendar_date": "2026-01-01",
    }
    
    result = await graph.ainvoke(state, config=config)
    
    # Should retry exactly 2 times (so retry_count is 2)
    assert result["reviewer_retry_count"] == 2
    assert result["reviewer_passed"] is False
    assert result["reviewer_score"] == 50

@pytest.mark.asyncio
@patch("app.services.generation.nodes.get_chat_model")
@patch("app.services.generation.nodes.retrieve_context")
async def test_strategy_fallback(mock_retrieve, mock_get_model, workspace, checkpointer, db):
    mock_retrieve.return_value = []
    # Insert recent posts
    p1 = GeneratedPost(workspace_id=workspace.id, generation_cycle_id=uuid.uuid4(), content_type="educational", status="PUBLISHED")
    p2 = GeneratedPost(workspace_id=workspace.id, generation_cycle_id=uuid.uuid4(), content_type="promotional", status="PUBLISHED")
    db.add_all([p1, p2])
    db.commit()
    
    def side_effect(purpose):
        if purpose == "strategist":
            # Force LLM failure
            return MockModel(Exception("LLM down"))
        elif purpose == "writer":
            return MockModel(MagicMock(caption="Test", hashtags=[], cta="", needs_image=False))
        elif purpose == "reviewer":
            return MockModel(MagicMock(score=100, notes=""))
            
    mock_get_model.side_effect = side_effect
    
    graph = get_compiled_graph(checkpointer=checkpointer)
    cycle_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": cycle_id}}
    
    state = {
        "workspace_id": str(workspace.id),
        "generation_cycle_id": cycle_id,
        "calendar_date": "2026-01-01",
    }
    
    result = await graph.ainvoke(state, config=config)
    
    # Fallback should pick something not heavily used. 'educational' and 'promotional' were used.
    # It could be 'behind_the_scenes' etc.
    assert result["content_type"] not in ["educational", "promotional"]
    assert "Fallback" in result["content_type_rationale"]

def test_provider_swap():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test"}):
        model = get_chat_model("strategist")
        from langchain_openai import ChatOpenAI
        assert isinstance(model, ChatOpenAI)
        
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test"}):
        model = get_chat_model("writer")
        from langchain_anthropic import ChatAnthropic
        assert isinstance(model, ChatAnthropic)

    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test"}):
        model = get_chat_model("reviewer")
        from langchain_google_genai import ChatGoogleGenerativeAI
        assert isinstance(model, ChatGoogleGenerativeAI)
