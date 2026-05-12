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
    """Format an event dict as a single SSE frame.

    ``event["event"]`` becomes the ``event:`` line, ``event["data"]`` is JSON-
    encoded onto a single ``data:`` line. The blank trailing line terminates
    the frame per the EventStream spec.
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
    """Streaming variant of /run. Emits SSE events while the agent works so
    the chat UI can show phased status ("正在思考……" → "正在查询岗位……" →
    "正在整理回答……") instead of waiting 30+ seconds in silence.

    Event schema is documented on ``run_assistant_turn_stream``.
    """

    async def event_stream() -> AsyncIterator[str]:
        async for event in run_assistant_turn_stream(db, current_user, payload):
            yield _encode_sse(event)

    # ``X-Accel-Buffering: no`` disables nginx/CDN response buffering so each
    # frame reaches the browser as soon as it is yielded. The default Cache-
    # Control header would otherwise let an intermediary buffer the whole
    # response and defeat the point of streaming.
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
