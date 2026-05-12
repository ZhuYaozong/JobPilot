"""HTTP-layer tests for POST /api/v1/assistant/run.

A multi-prompt fake LLM (dispatch on a unique marker in the prompt) lets us
verify the full e2e: user message persisted, agent_run created, workflow
runs, tool called, assistant message stored, response shape correct.
"""

import asyncio
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.client import LLMClient, LLMConfigError
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.message import Message
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_PARSED_RESUME: dict[str, Any] = {
    "summary": "Backend engineer.",
    "skills": ["FastAPI"],
    "experiences": [],
    "projects": [],
    "education": [],
    "target_roles": ["AI Application Engineer"],
    "years_of_experience": "2 years",
}

_PARSED_JOB: dict[str, Any] = {
    "summary": "Build AI workflow apps.",
    "responsibilities": [],
    "required_skills": ["FastAPI"],
    "preferred_skills": [],
    "keywords": [],
    "seniority": "junior-mid",
    "city": "Shanghai",
}

_MATCH_LLM_JSON = (
    '{"overall_score": 81, "strengths": ["FastAPI"], "weaknesses": [],'
    ' "missing_keywords": [], "suggestions": []}'
)


async def _seed_resume_and_job(
    db: AsyncSession, marker: str,
) -> tuple[User, int, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    resume = Resume(
        user_id=user.id,
        title=f"{marker} resume",
        raw_text="FastAPI experience.",
        content_hash=f"{marker}-asst-res",
        source_type="manual",
        parsed_json=_PARSED_RESUME,
        parse_status="parsed",
    )
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} company",
        job_title="AI Application Engineer",
        city="Shanghai",
        jd_text="Build AI workflow apps.",
        parsed_json=_PARSED_JOB,
    )
    db.add(resume)
    db.add(job)
    await db.commit()
    await db.refresh(resume)
    await db.refresh(job)
    return user, resume.id, job.id


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


_EMPTY_TOOL_HISTORY_MARKER = "(本轮还没有调用过工具)"


def _make_fake_llm(
    *,
    decide_response: str,
    final_text: str = "已为你完成。",
    follow_up_response: str | None = None,
    match_response: str = _MATCH_LLM_JSON,
):
    """Build a stateless fake LLM that dispatches on prompt markers.

    The ReAct loop now calls ``decide`` again after every tool, so we
    distinguish the initial decide (tool_call_history empty) from follow-up
    decides (history non-empty). By default the follow-up decide returns a
    ``respond_directly`` envelope so the loop terminates cleanly after one
    tool. ``final_text`` is the text shown to the user as the assistant reply
    on that respond_directly path. Tests that want a different terminating
    text or a multi-tool flow can override ``follow_up_response`` directly.
    """
    default_follow_up = (
        '{"action": "respond_directly", "text": ' + repr(final_text).replace("'", '"') + "}"
    )
    follow_up = follow_up_response if follow_up_response is not None else default_follow_up

    async def fake(self, prompt: str) -> str:
        if "Compare the structured resume" in prompt:
            return match_response
        if "本轮你为了回答用户的问题" in prompt:
            return final_text
        if "请严格按以下两种 JSON 之一回复" in prompt:
            if _EMPTY_TOOL_HISTORY_MARKER in prompt:
                return decide_response
            return follow_up
        raise AssertionError(f"unexpected LLM prompt:\n{prompt[:200]}")

    return fake


def test_assistant_run_happy_path_calls_tool_and_writes_assistant_message(
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
        "/api/v1/assistant/run",
        json={"content": f"分析简历 {resume_id} 对岗位 {job_id} 的匹配度"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["conversation_id"] > 0
    assert body["agent_run"]["status"] == "succeeded"
    assert body["agent_run"]["intent"] == "analyze_match"
    assert len(body["agent_run"]["tool_calls"]) == 1
    tool_call = body["agent_run"]["tool_calls"][0]
    assert tool_call["tool_name"] == "analyze_match"
    assert tool_call["status"] == "success"
    assert tool_call["latency_ms"] is not None
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"] is not None
    assert body["assistant_message"]["role"] == "assistant"
    assert "81" in body["assistant_message"]["content"]


def test_assistant_run_creates_conversation_when_id_is_null(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response='{"action": "respond_directly", "text": "你好,有什么需要我帮忙的?"}',
        ),
    )

    response = client.post(
        "/api/v1/assistant/run",
        json={"content": f"{test_marker} hello"},
    )
    assert response.status_code == 200
    body = response.json()
    new_conversation_id = body["conversation_id"]

    # A second request with that conversation_id should append to it, not
    # create a new one.
    second = client.post(
        "/api/v1/assistant/run",
        json={
            "conversation_id": new_conversation_id,
            "content": f"{test_marker} follow-up",
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == new_conversation_id

    # sequence_no should be 1,2,3,4 across the two turns.
    msgs = client.get(
        f"/api/v1/conversations/{new_conversation_id}/messages",
    ).json()
    assert [m["sequence_no"] for m in msgs] == [1, 2, 3, 4]


def test_assistant_run_rejects_other_users_conversation(
    client: TestClient,
    test_marker: str,
) -> None:
    response = client.post(
        "/api/v1/assistant/run",
        json={"conversation_id": 999_999_999, "content": f"{test_marker} probe"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_assistant_run_marks_agent_run_failed_when_llm_misconfigured(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    async def broken(self, prompt: str) -> str:
        raise LLMConfigError("LLM configuration is incomplete")

    monkeypatch.setattr(LLMClient, "generate_text", broken)

    response = client.post(
        "/api/v1/assistant/run",
        json={"content": f"{test_marker} doomed"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_run"]["status"] == "failed"
    assert body["agent_run"]["error_class"] == "llm_config_missing"
    assert body["assistant_message"] is None
    # user_message should still have been written.
    assert body["user_message"]["content"].endswith("doomed")


def test_assistant_run_handles_tool_business_error_via_format_response(
    client: TestClient,
    monkeypatch,
    test_marker: str,
) -> None:
    # decide picks the tool, but with a nonexistent resume_id. The tool
    # returns ok=False, which format_response should turn into a sensible
    # natural-language reply. Run still succeeds at the agent level.
    decide_json = (
        '{"action": "call_tool", "tool": "analyze_match",'
        ' "args": {"resume_id": 999999999, "job_posting_id": 999999998}}'
    )
    monkeypatch.setattr(
        LLMClient,
        "generate_text",
        _make_fake_llm(
            decide_response=decide_json,
            final_text="看起来这份简历好像不存在,你确认一下 id 再试试?",
        ),
    )

    response = client.post(
        "/api/v1/assistant/run",
        json={"content": f"{test_marker} bad ids"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_run"]["status"] == "succeeded"
    assert body["assistant_message"] is not None
    assert "确认" in body["assistant_message"]["content"]
    assert len(body["agent_run"]["tool_calls"]) == 1
    assert body["agent_run"]["tool_calls"][0]["status"] == "failed"
    assert body["agent_run"]["tool_calls"][0]["error_class"] == "resume_not_found"
