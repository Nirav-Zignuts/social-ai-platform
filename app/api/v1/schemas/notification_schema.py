from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    workspace_id: UUID
    post_id: Optional[UUID]
    type: str
    channel: str
    read_at: Optional[datetime]
    sent_at: Optional[datetime]
    payload: Optional[dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
