import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.middlewares.auth_middleware import require_auth
from app.models.generated_post import GeneratedPost
from app.core.enums import GeneratedPostStatus


@pytest.fixture
def post(db, workspace):
    p = GeneratedPost(
        workspace_id=workspace.id,
        generation_cycle_id=uuid.uuid4(),
        caption="Caption",
        status=GeneratedPostStatus.PENDING_REVIEW.value,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def client(db, user):
    app.dependency_overrides[require_auth] = lambda: {"user_id": str(user.id)}
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_regenerate_without_feedback_returns_422(client, workspace, post):
    response = client.post(
        f"/api/v1/workspaces/{workspace.id}/generated-posts/{post.id}/review/regenerate",
        json={},
    )
    assert response.status_code == 422
