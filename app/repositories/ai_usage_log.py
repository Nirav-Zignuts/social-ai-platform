from sqlalchemy.orm import Session

from app.models.ai_usage_log import AIUsageLog


class AIUsageLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: AIUsageLog) -> AIUsageLog:
        self.db.add(row)
        return row
