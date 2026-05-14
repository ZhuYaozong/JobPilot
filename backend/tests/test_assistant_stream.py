"""Tests for POST /api/v1/assistant/run-stream.

The streaming endpoint runs the same workflow as /run but emits SSE events
along the way so the chat UI can show phased status. These tests verify the
event protocol: shape, ordering, and the final ``message`` / ``error`` /
``done`` events. The shared workflow + persistence logic is already covered
by tests/test_assistant_api.py.
"""

import asyncio
import json
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.client import LLMClient, LLMConfigError

from tests.test_assistant_api import (
    _EMPTY_TOOL_HISTORY_MARKER,
    _MATCH_LLM_JSON,
    _seed_resume_and_job,
)


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _make_fake_llm(
    *,
    decide_response: str,
    final_text: str = "已为你完成。",
    follow_up_response: str | None = None,
):
    """Copy of test_assistant_api._make_fake_llm.

    We duplicate rather than import to keep this file self-contained — the
    helper builds a closure over module-scoped state in the other file and
    re-using it through pytest fixtures gets noisy.
    """
    default_follow_up = (
        '{"action": "respond_directly", "text": '
        + repr(final_text).replace("'", '"')
        + "}"
    )
    follow_up = (
        follow_up_response if follow_up_response is not None else default_follow_up
    )

    async def fake(self, prompt: str) -> str:
        if "请比较结构化简历" in prompt:
            return _MATCH_LLM_JSON
        if "本轮你为了回答用户的问题" in prompt:
            return final_text
        if "请严格按以下两种 JSON 之一回复" in prompt:
            if _EMPTY_TOOL_HISTORY_MARKER in prompt:
                return decide_response
            return follow_up
        raise AssertionError(f"unexpected LLM prompt:\n{prompt[:200]}")

    return fake


def _parse_sse_stream(raw: str) -> list[tuple[str, dict]]:
    """Parse the raw text body of an SSE response into ``[(event, data)]``.

    The server always emits one ``event:`` + one ``data:`` line per frame,
    separated by blank lines — exactly what the client-side parser handles.
    """
    events: list[tuple[str, dict]] = []
    for chunk in raw.split("\n\n"):
        if not chunk.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            continue
        data = json.loads("\n".join(data_lines))
        events.append((event_name, data))
    return events


def test_assistant_run_stream_happy_path_emits_phase_and_tool_events(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    seed = _run(lambda db: _seed_resume_and_job(db, test_marker))
    _user, resume_id, job_id = seed

    decide_json = (
        '{"action": "call_tool", "tool": "analyze_match",'
        f' "args": {{"resume_id": {resume_id}, "job_posting_id": {job_id}}}}}'
    )
    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response=decide_json,
            final_text=f"你的简历对岗位 {job_id} 综合得分 81 分。",
        ),
    )

    response = client.post(
        "/api/v1/assistant/run-stream",
        json={"content": f"分析简历 {resume_id} 对岗位 {job_id} 的匹配度"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_stream(response.text)
    event_names = [name for name, _ in events]

    # First event is always ``started`` with the persisted user message.
    assert event_names[0] == "started"
    started_data = events[0][1]
    assert started_data["conversation_id"] > 0
    assert started_data["user_message"]["role"] == "user"
    assert str(resume_id) in started_data["user_message"]["content"]

    # The ReAct loop emits at least one ``phase`` event before the tool call.
    assert "phase" in event_names
    assert "tool_call_started" in event_names
    assert "tool_call_completed" in event_names

    # The tool_call_completed event should mention the right tool & ok=True.
    tool_completed = next(
        data for name, data in events if name == "tool_call_completed"
    )
    assert tool_completed["tool_name"] == "analyze_match"
    assert tool_completed["ok"] is True

    # Stream terminates with message + done.
    assert event_names[-2] == "message"
    assert event_names[-1] == "done"
    message_data = events[-2][1]
    assert message_data["assistant_message"]["role"] == "assistant"
    assert "81" in message_data["assistant_message"]["content"]
    assert message_data["agent_run"]["status"] == "succeeded"
    assert message_data["agent_run"]["intent"] == "analyze_match"
    assert len(message_data["agent_run"]["tool_calls"]) == 1


def test_assistant_run_stream_respond_directly_skips_tool_events(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    """When decide says respond_directly, no tool_call_* events should fire
    and the formatting phase should be skipped (it's only emitted on the
    LLM-driven format path)."""
    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response=(
                '{"action": "respond_directly", "text": "你好，有什么需要我帮忙的？"}'
            ),
        ),
    )

    response = client.post(
        "/api/v1/assistant/run-stream",
        json={"content": f"{test_marker} hello"},
    )
    assert response.status_code == 200

    events = _parse_sse_stream(response.text)
    event_names = [name for name, _ in events]

    assert event_names[0] == "started"
    # No tool calls anywhere.
    assert "tool_call_started" not in event_names
    assert "tool_call_completed" not in event_names
    # Decide ran (phase: deciding), but no formatting phase (early return).
    deciding_phases = [data for name, data in events if name == "phase"]
    assert all(d["phase"] == "deciding" for d in deciding_phases)

    assert event_names[-2] == "message"
    assert event_names[-1] == "done"
    message_data = events[-2][1]
    assert "你好" in message_data["assistant_message"]["content"]


def test_assistant_run_stream_emits_error_event_when_llm_misconfigured(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    async def broken(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", broken)

    response = client.post(
        "/api/v1/assistant/run-stream",
        json={"content": f"{test_marker} doomed"},
    )
    assert response.status_code == 200

    events = _parse_sse_stream(response.text)
    event_names = [name for name, _ in events]

    assert event_names[0] == "started"
    # No tool calls, no message — straight to error then done.
    assert event_names[-2] == "error"
    assert event_names[-1] == "done"

    error_data = events[-2][1]
    assert error_data["error_class"] == "llm_config_missing"
    assert error_data["agent_run"]["status"] == "failed"
