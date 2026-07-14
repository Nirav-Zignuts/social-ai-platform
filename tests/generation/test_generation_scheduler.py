from datetime import date, datetime, time, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.generation.scheduler import (
    compute_target_generation_time,
    find_generation_due_workspaces,
    get_workspace_local_now,
    is_generation_due,
)
from app.models.workspace import Workspace


def test_compute_target_crosses_into_previous_local_day():
    """preferred=06:00, lead=12 → target is 18:00 the previous local day."""
    tz = ZoneInfo("America/New_York")
    local_now = datetime(2026, 7, 13, 10, 0, tzinfo=tz)

    target = compute_target_generation_time(
        local_now=local_now,
        preferred_post_time=time(6, 0),
        generation_lead_hours=12,
    )

    assert target == datetime(2026, 7, 12, 18, 0, tzinfo=tz)
    assert target.date() == date(2026, 7, 12)
    assert target.date() < local_now.date()


def test_compute_target_same_local_day():
    """preferred=18:00, lead=12 → target is 06:00 same local day."""
    tz = ZoneInfo("UTC")
    local_now = datetime(2026, 7, 13, 12, 0, tzinfo=tz)

    target = compute_target_generation_time(
        local_now=local_now,
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
    )

    assert target == datetime(2026, 7, 13, 6, 0, tzinfo=tz)
    assert target.date() == local_now.date()


def test_is_generation_due_when_past_yesterday_target(db, user):
    """
    At local evening after the crossed-day target, generation should be due
    once for that local calendar day.
    """
    tz_name = "America/New_York"
    workspace = Workspace(
        name="Sched WS",
        slug="sched-ws-cross-day",
        owner_id=user.id,
        timezone=tz_name,
        preferred_post_time=time(6, 0),
        generation_lead_hours=12,
        status="active",
        onboarding_status="completed",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    # 2026-07-13 19:00 EDT — after previous-day 18:00 target for today's 06:00 publish
    utc_now = datetime(2026, 7, 13, 23, 0, tzinfo=timezone.utc)  # 19:00 EDT
    is_due, local_today, target = is_generation_due(workspace, utc_now=utc_now)

    assert is_due is True
    assert local_today == date(2026, 7, 13)
    assert target == datetime(2026, 7, 12, 18, 0, tzinfo=ZoneInfo(tz_name))


def test_is_generation_due_false_before_same_day_target(db, user):
    workspace = Workspace(
        name="Sched WS2",
        slug="sched-ws-same-day",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
        status="active",
        onboarding_status="completed",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    # 05:00 UTC — before 06:00 target for 18:00 publish with 12h lead
    utc_now = datetime(2026, 7, 13, 5, 0, tzinfo=timezone.utc)
    is_due, local_today, target = is_generation_due(workspace, utc_now=utc_now)

    assert is_due is False
    assert local_today == date(2026, 7, 13)
    assert target == datetime(2026, 7, 13, 6, 0, tzinfo=ZoneInfo("UTC"))


def test_is_generation_due_false_when_already_generated_today(db, user):
    workspace = Workspace(
        name="Sched WS3",
        slug="sched-ws-already",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
        last_generation_date=date(2026, 7, 13),
        status="active",
        onboarding_status="completed",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    utc_now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    is_due, _, _ = is_generation_due(workspace, utc_now=utc_now)
    assert is_due is False


def test_find_generation_due_workspaces_filters(db, user):
    due_ws = Workspace(
        name="Due",
        slug="due-gen-ws",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
        status="active",
        onboarding_status="completed",
    )
    incomplete = Workspace(
        name="Incomplete",
        slug="incomplete-gen-ws",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
        status="active",
        onboarding_status="ai_configured",
    )
    no_time = Workspace(
        name="NoTime",
        slug="notime-gen-ws",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=None,
        generation_lead_hours=12,
        status="active",
        onboarding_status="completed",
    )
    db.add_all([due_ws, incomplete, no_time])
    db.commit()

    utc_now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    due = find_generation_due_workspaces(db, utc_now=utc_now)
    due_ids = {ws.id for ws, _ in due}

    assert due_ws.id in due_ids
    assert incomplete.id not in due_ids
    assert no_time.id not in due_ids


@patch("app.generation.tasks.find_generation_due_workspaces")
def test_poll_generation_due_stamps_last_generation_date(mock_find, db, user):
    from app.generation.tasks import poll_generation_due

    workspace = Workspace(
        name="Poll Stamp",
        slug="poll-stamp-ws",
        owner_id=user.id,
        timezone="UTC",
        preferred_post_time=time(18, 0),
        generation_lead_hours=12,
        status="active",
        onboarding_status="completed",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    class SessionProxy:
        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            return None

        def query(self, *args, **kwargs):
            return db.query(*args, **kwargs)

        def add(self, obj):
            return db.add(obj)

        def commit(self):
            return db.commit()

    mock_find.return_value = [(workspace, date(2026, 7, 13))]
    with patch("app.generation.tasks.SessionLocal", return_value=SessionProxy()):
        result = poll_generation_due()

    db.refresh(workspace)
    assert workspace.last_generation_date == date(2026, 7, 13)
    assert result["workspace_ids"] == [str(workspace.id)]
    assert result["enqueued"] == 1


def test_get_workspace_local_now_converts_utc(db, user):
    workspace = Workspace(
        name="TZ",
        slug="tz-ws",
        owner_id=user.id,
        timezone="Asia/Kolkata",
        preferred_post_time=time(9, 0),
        status="active",
        onboarding_status="completed",
    )
    utc_now = datetime(2026, 7, 13, 6, 30, tzinfo=timezone.utc)
    local = get_workspace_local_now(workspace, utc_now=utc_now)
    assert local.tzinfo == ZoneInfo("Asia/Kolkata")
    assert local.hour == 12
    assert local.minute == 0
