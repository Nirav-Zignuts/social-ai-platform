from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.workspace import Workspace

logger = logging.getLogger(__name__)


def get_workspace_local_now(workspace: Workspace, *, utc_now: datetime | None = None) -> datetime:
    """Return timezone-aware 'now' in the workspace's local timezone."""
    utc_now = utc_now or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    tz = ZoneInfo(workspace.timezone or "UTC")
    return utc_now.astimezone(tz)


def compute_target_generation_time(
    *,
    local_now: datetime,
    preferred_post_time: time,
    generation_lead_hours: int,
) -> datetime:
    """
    Compute when generation should fire for the current local calendar day.

    target = (local_today at preferred_post_time) - lead_hours

    Example: preferred=06:00, lead_hours=12 → target is 18:00 on the previous
    local calendar day (not a naive time-of-day wrap).
    """
    if local_now.tzinfo is None:
        raise ValueError("local_now must be timezone-aware")
    local_today = local_now.date()
    publish_slot_today = datetime.combine(
        local_today,
        preferred_post_time,
        tzinfo=local_now.tzinfo,
    )
    return publish_slot_today - timedelta(hours=generation_lead_hours)


def is_generation_due(
    workspace: Workspace,
    *,
    utc_now: datetime | None = None,
) -> tuple[bool, date | None, datetime | None]:
    """
    Return (is_due, local_today, target_generation_time).

    is_due when local now has reached the lead-adjusted target and we have not
    already recorded generation for today's local calendar date.
    """
    if not workspace.preferred_post_time:
        return False, None, None

    local_now = get_workspace_local_now(workspace, utc_now=utc_now)
    local_today = local_now.date()
    lead_hours = workspace.generation_lead_hours or 12
    target = compute_target_generation_time(
        local_now=local_now,
        preferred_post_time=workspace.preferred_post_time,
        generation_lead_hours=lead_hours,
    )
    if workspace.last_generation_date == local_today:
        return False, local_today, target

    if local_now >= target:
        return True, local_today, target

    return False, local_today, target


def find_generation_due_workspaces(
    db: Session,
    *,
    utc_now: datetime | None = None,
) -> list[tuple[Workspace, date]]:
    """
    Active, onboarded workspaces that are due for generation right now.

    Returns list of (workspace, local_today) so callers can stamp
    last_generation_date before enqueueing.
    """
    workspaces = (
        db.query(Workspace)
        .filter(
            Workspace.status == "active",
            Workspace.onboarding_status == "completed",
            Workspace.preferred_post_time.is_not(None),
            Workspace.is_deleted.is_(False),
        )
        .all()
    )

    due: list[tuple[Workspace, date]] = []
    for workspace in workspaces:
        is_due, local_today, _target = is_generation_due(workspace, utc_now=utc_now)
        if is_due and local_today is not None:
            due.append((workspace, local_today))
    return due
