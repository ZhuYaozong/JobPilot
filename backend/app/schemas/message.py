from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    conversation_id: int
    role: str
    content: str
    sequence_no: int
    content_json: dict[str, Any] | None = None
    agent_run_id: int | None = None


class MessageListItem(BaseModel):
    id: int
    conversation_id: int
    role: str
    sequence_no: int
    agent_run_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageRead(MessageListItem):
    content: str
    content_json: dict[str, Any] | None
