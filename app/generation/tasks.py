import logging

from app.db.session import SessionLocal
from app.generation.scheduler import find_generation_due_workspaces

logger = logging.getLogger(__name__)


def poll_generation_due() -> dict:
    """
    Find workspaces due for daily generation and stamp last_generation_date.

    Caller should schedule run_generation_cycle via BackgroundTasks for each id.
    Stamping before enqueue prevents double-trigger within the same local day.
    """
    db = SessionLocal()
    enqueued: list[str] = []
    try:
        print("Finding generation due workspaces")
        due = find_generation_due_workspaces(db)
        print(f"Found {len(due)} workspaces")
        for workspace, local_today in due:
            workspace.last_generation_date = local_today
            db.add(workspace)
            db.commit()

            enqueued.append(str(workspace.id))
            logger.info(
                "poll_generation_due stamped workspace=%s local_date=%s",
                workspace.id,
                local_today,
            )

        return {"enqueued": len(enqueued), "workspace_ids": enqueued}
    finally:
        db.close()
