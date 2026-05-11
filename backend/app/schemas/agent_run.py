from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentRunCreate(BaseModel):
    conversation_id: int
    trigger_message_id: int | None = None
    intent: str | None = None


class AgentRunUpdate(BaseModel):
    status: str | None = None
    intent: str | None = None
    error_class: str | None = None
    error_detail: str | None = None
    token_usage: dict[str, Any] | None = None
    finished_at: datetime | None = None


class AgentRunListItem(BaseModel):
    id: int
    conversation_id: int
    trigger_message_id: int | None
    status: str
    intent: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(AgentRunListItem):
    error_class: str | None
    error_detail: str | None
    token_usage: dict[str, Any] | None
