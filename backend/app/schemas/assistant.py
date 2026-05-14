from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageRead

AssistantMode = Literal["chat", "mock_interview"]


class ContextSelection(BaseModel):
    """前端可选传入的上下文选择。

    服务端会把这些 id 解析成人类可读提示，再拼到 user_text 前喂给 workflow。
    这样 Agent 既能看到用户原始问题，也能知道“当前选中了简历 #7 和岗位 #12”。
    """

    assistant_mode: AssistantMode | None = None
    resume_id: int | None = None
    job_posting_id: int | None = None
    application_record_id: int | None = None
    knowledge_base_id: int | None = None


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
    # 如果本轮在助手回复前失败，这里为 None。
    assistant_message: MessageRead | None
