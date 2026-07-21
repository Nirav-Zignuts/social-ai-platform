from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin_action_log import AdminActionLog
from app.repositories.admin_action_log import AdminActionLogRepository


def log_admin_action(
    db: Session,
    *,
    admin_id: UUID,
    action_type: str,
    target_type: str,
    target_id: UUID,
    reason: str,
    payload_snapshot: dict | None = None,
) -> AdminActionLog:
    row = AdminActionLog(
        admin_id=admin_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        reason=reason.strip(),
        payload_snapshot=payload_snapshot,
    )
    return AdminActionLogRepository(db).add(row)
