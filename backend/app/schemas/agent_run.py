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


class ToolCallLogRead(BaseModel):
    """单次工具调用的完整持久化视图。

    与 SSE 实时事件互补:实时事件只带 tool_name / status / error_class / latency_ms
    用于轻量进度提示;本 schema 含 arguments_json / result_json / error_detail,
    支持前端点击 trace 时展开看完整内容(任务 4 Agent 可观测)。
    """

    id: int
    tool_name: str
    status: str
    arguments_json: dict[str, Any]
    result_json: dict[str, Any] | None
    error_class: str | None
    error_detail: str | None
    started_at: datetime
    finished_at: datetime | None
    latency_ms: int | None

    model_config = ConfigDict(from_attributes=True)


class AgentRunWithToolCallsRead(AgentRunRead):
    """一次 Agent 运行的元数据 + 该运行内所有工具调用(按时间序)。"""

    tool_calls: list[ToolCallLogRead]
