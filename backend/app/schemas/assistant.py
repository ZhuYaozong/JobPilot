from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageRead


class AssistantRunRequest(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=8000)


class ToolCallTrace(BaseModel):
    id: int
    tool_name: str
    status: str
    error_class: str | None
    latency_ms: int | None

    model_config = ConfigDict(from_attributes=True)


class AgentRunSummary(BaseModel):
    id: int
    status: str
    intent: str | None
    started_at: datetime
    finished_at: datetime | None
    error_class: str | None
    error_detail: str | None
    tool_calls: list[ToolCallTrace]


class AssistantRunResponse(BaseModel):
    conversation_id: int
    agent_run: AgentRunSummary
    user_message: MessageRead
    # Null when the run failed before the assistant could reply.
    assistant_message: MessageRead | None
