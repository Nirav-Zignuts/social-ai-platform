import uuid

import pytest
from sqlalchemy.orm import configure_mappers, Session

from app.db.models import *  # noqa: F401,F403
from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace

configure_mappers()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def user(db: Session):
    u = User(email=f"{uuid.uuid4()}@test.com", full_name="Test User")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def other_user(db: Session):
    u = User(email=f"{uuid.uuid4()}@test.com", full_name="Other User")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def workspace(db: Session, user: User):
    ws = Workspace(
        name="Test WS",
        slug=f"test-ws-{uuid.uuid4()}",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time="12:00:00",
        require_human_approval=True,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws
