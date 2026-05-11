from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCallLogCreate(BaseModel):
    agent_run_id: int
    tool_name: str
    arguments_json: dict[str, Any]


class ToolCallLogUpdate(BaseModel):
    status: str | None = None
    result_json: dict[str, Any] | None = None
    error_class: str | None = None
    error_detail: str | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None


class ToolCallLogListItem(BaseModel):
    id: int
    agent_run_id: int
    tool_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    latency_ms: int | None

    model_config = ConfigDict(from_attributes=True)


class ToolCallLogRead(ToolCallLogListItem):
    arguments_json: dict[str, Any]
    result_json: dict[str, Any] | None
    error_class: str | None
    error_detail: str | None
