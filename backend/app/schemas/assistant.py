from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageRead


class ContextSelection(BaseModel):
    """Optional UI-side context. The server stitches a human-readable hint
    onto the user_text before feeding it to the workflow, so the agent sees
    "user selected resume #7 and job #12" alongside the actual question."""

    resume_id: int | None = None
    job_posting_id: int | None = None
    application_record_id: int | None = None


class AssistantRunRequest(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=8000)
    context: ContextSelection | None = None


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
