import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDep, DbSession
from app.schemas.assistant import AssistantRunRequest, AssistantRunResponse
from app.services.assistant_service import (
    run_assistant_turn,
    run_assistant_turn_stream,
)

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/run", response_model=AssistantRunResponse)
async def run_assistant(
    payload: AssistantRunRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> AssistantRunResponse:
    return await run_assistant_turn(db, current_user, payload)


def _encode_sse(event: dict[str, Any]) -> str:
    """把事件字典编码成单个 SSE frame。

    ``event["event"]`` 会写入 ``event:`` 行，``event["data"]`` 会 JSON 编码后写入
    单行 ``data:``。末尾空行是 EventStream 协议要求的 frame 结束标记。
    """
    event_type = event.get("event") or "message"
    payload = json.dumps(event.get("data") or {}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/run-stream")
async def run_assistant_stream(
    payload: AssistantRunRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    """``/run`` 的流式版本，在 Agent 工作时持续发出 SSE 事件。

    前端可以据此展示“正在思考 → 正在查询岗位 → 正在整理回答”等阶段状态，而不是让
    用户在长工具链期间等待一整个空白请求。事件结构由 ``run_assistant_turn_stream``
    统一定义。
    """

    async def event_stream() -> AsyncIterator[str]:
        async for event in run_assistant_turn_stream(db, current_user, payload):
            yield _encode_sse(event)

    # ``X-Accel-Buffering: no`` 关闭 nginx/CDN 缓冲，确保每个 frame yield 后尽快到浏览器。
    # Cache-Control 也显式禁用缓存，避免中间层把整段响应攒完再发，破坏流式体验。
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
