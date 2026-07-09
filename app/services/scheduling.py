from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models.workspace import Workspace


def calculate_next_scheduled_time(workspace: Workspace) -> datetime:
    """Return the next publish slot in UTC based on workspace timezone and preferred_post_time."""
    tz = ZoneInfo(workspace.timezone or "UTC")
    now_local = datetime.now(tz)
    preferred: time = workspace.preferred_post_time or time(9, 0)

    candidate = now_local.replace(
        hour=preferred.hour,
        minute=preferred.minute,
        second=getattr(preferred, "second", 0) or 0,
        microsecond=0,
    )

    if candidate <= now_local:
        candidate += timedelta(days=1)

    return candidate.astimezone(ZoneInfo("UTC"))
