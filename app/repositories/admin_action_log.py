from sqlalchemy.orm import Session

from app.models.admin_action_log import AdminActionLog


class AdminActionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: AdminActionLog) -> AdminActionLog:
        self.db.add(row)
        self.db.flush()
        return row
