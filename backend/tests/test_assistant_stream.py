"""POST /api/v1/assistant/run-stream 的测试。

流式 endpoint 与 /run 使用同一套 workflow，但会在执行过程中发出 SSE 事件，
让聊天 UI 能显示阶段状态。这些测试验证事件协议：形状、顺序，以及最终的
``message`` / ``error`` / ``done`` 事件。共享的工作流与持久化逻辑已经由
tests/test_assistant_api.py 覆盖。
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
    """test_assistant_api._make_fake_llm 的本地模拟副本。

    这里选择复制而不是导入，是为了让本文件保持自包含；另一个 helper 会闭包捕获
    对方模块级状态，跨 pytest fixture 复用会让测试关系变得嘈杂。
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
    """把 SSE 响应的原始文本解析成 ``[(event, data)]``。

    服务端每帧固定发出一行 ``event:`` 和一行 ``data:``，帧之间用空行分隔；
    这与客户端解析器处理的协议一致。
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

    # 第一个事件始终是 ``started``，并携带已持久化的用户消息。
    assert event_names[0] == "started"
    started_data = events[0][1]
    assert started_data["conversation_id"] > 0
    assert started_data["user_message"]["role"] == "user"
    assert str(resume_id) in started_data["user_message"]["content"]

    # ReAct 循环在工具调用前至少会发出一个 ``phase`` 事件。
    assert "phase" in event_names
    assert "tool_call_started" in event_names
    assert "tool_call_completed" in event_names

    # tool_call_completed 事件应包含正确工具名，并且 ok=True。
    tool_completed = next(
        data for name, data in events if name == "tool_call_completed"
    )
    assert tool_completed["tool_name"] == "analyze_match"
    assert tool_completed["ok"] is True

    # 流式响应应以 message + done 收尾。
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
    """decide 返回 respond_directly 时，不应发出 tool_call_* 事件。

    formatting 阶段也应被跳过，因为它只在 LLM 驱动的 format 路径上发出。
    """
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
    # 全程不应有任何工具调用。
    assert "tool_call_started" not in event_names
    assert "tool_call_completed" not in event_names
    # decide 已执行（phase: deciding），但由于提前返回，没有 formatting 阶段。
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
    # 没有工具调用，也没有 message，直接 error 后 done。
    assert event_names[-2] == "error"
    assert event_names[-1] == "done"

    error_data = events[-2][1]
    assert error_data["error_class"] == "llm_config_missing"
    assert error_data["agent_run"]["status"] == "failed"
