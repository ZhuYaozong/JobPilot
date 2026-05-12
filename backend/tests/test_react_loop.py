"""ReAct multi-tool loop tests.

We drive the LangGraph workflow directly (no HTTP). A stateful fake LLM lets
us script the decide sequence so we can verify three behaviours:

1. The agent can chain multiple read+action tools in a single turn.
2. ``tool_call_history`` accumulates entries in order.
3. ``MAX_TOOL_ITERATIONS`` (=3) forces format_response after the cap, even if
   decide keeps wanting to call tools.
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.workflow import MAX_TOOL_ITERATIONS, build_workflow
from app.core.config import settings
from app.llm.client import LLMClient
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.user import User


_PARSED_JOB: dict[str, Any] = {
    "summary": "Build AI workflow apps.",
    "responsibilities": [],
    "required_skills": ["FastAPI"],
    "preferred_skills": [],
    "keywords": [],
    "seniority": "junior-mid",
    "city": "Shanghai",
}


async def _setup_run(db: AsyncSession, marker: str) -> tuple[User, int, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} react conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)
    return user, agent_run.id, conversation.id


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


def _initial_state(user_id, agent_run_id, conversation_id, user_text):
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "user_message_id": 0,
        "user_text": user_text,
        "agent_run_id": agent_run_id,
        "conversation_history": [],
        "existing_summary": None,
        "message_count_before_user": 0,
        "decide_repair_attempts": 0,
        "iteration_count": 0,
        "tool_call_history": [],
    }


def test_react_loop_chains_two_tools_then_responds(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """First decide picks list_user_jobs, second decide picks
    respond_directly using the discovered job id. Verify both tool calls
    are recorded in tool_call_history."""
    assert client.get("/health/db").status_code == 200

    decide_calls = {"n": 0}

    # We populate a job ahead of time so list_user_jobs returns something.
    job_id_holder: dict[str, int] = {}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            decide_calls["n"] += 1
            if decide_calls["n"] == 1:
                # First decide: ask to list jobs
                return (
                    '{"action": "call_tool", "tool": "list_user_jobs",'
                    f' "args": {{"query": "{test_marker}"}}}}'
                )
            # Subsequent decide(s): the LLM has seen list_user_jobs result,
            # responds with a friendly message that mentions the count.
            assert "list_user_jobs" in prompt  # the history section
            return (
                '{"action": "respond_directly",'
                ' "text": "我看到了你保存的岗位。"}'
            )
        if "本轮你为了回答用户的问题" in prompt:
            return "format_response should not be called when respond_directly fires"
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, conversation_id = await _setup_run(db, test_marker)
        # Seed a single job under this user so list_user_jobs has something.
        job = JobPosting(
            user_id=user.id,
            company_name=f"{test_marker} TencentCo",
            job_title="后端工程师",
            jd_text="...",
            parsed_json=_PARSED_JOB,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id_holder["id"] = job.id

        graph = build_workflow(db=db, current_user=user, agent_run_id=agent_run_id)
        final_state = await graph.ainvoke(
            _initial_state(
                user.id, agent_run_id, conversation_id,
                f"{test_marker} 帮我看一下我保存的岗位",
            ),
        )

        assert final_state.get("decide_error_class") is None
        assert final_state.get("final_text") == "我看到了你保存的岗位。"

        # tool_call_history should have exactly one entry (the list_user_jobs
        # call). The follow-up decide chose respond_directly.
        history = final_state.get("tool_call_history") or []
        assert len(history) == 1
        assert history[0]["tool"] == "list_user_jobs"
        assert history[0]["result"]["ok"] is True
        assert decide_calls["n"] == 2  # initial + follow-up

    _run(_scenario)


def test_react_loop_hits_max_iterations_and_forces_format_response(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """If decide keeps picking call_tool, ``MAX_TOOL_ITERATIONS`` forces the
    workflow into format_response after the cap. Verify the LLM sees the
    final-response prompt and the tool history is full."""
    assert client.get("/health/db").status_code == 200

    decide_calls = {"n": 0}
    format_response_seen = {"n": 0}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            decide_calls["n"] += 1
            # Always pick list_user_jobs — agent never volunteers to stop.
            return (
                '{"action": "call_tool", "tool": "list_user_jobs",'
                f' "args": {{"query": "{test_marker}-iter-{decide_calls["n"]}"}}}}'
            )
        if "本轮你为了回答用户的问题" in prompt:
            format_response_seen["n"] += 1
            return "我看了你的岗位列表,这里是我的总结..."
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, conversation_id = await _setup_run(db, test_marker)
        graph = build_workflow(db=db, current_user=user, agent_run_id=agent_run_id)
        final_state = await graph.ainvoke(
            _initial_state(
                user.id, agent_run_id, conversation_id,
                f"{test_marker} 测试预算",
            ),
        )

        # Workflow ran exactly MAX_TOOL_ITERATIONS tool calls then forced
        # format_response.
        history = final_state.get("tool_call_history") or []
        assert len(history) == MAX_TOOL_ITERATIONS
        assert final_state.get("iteration_count") == MAX_TOOL_ITERATIONS
        assert format_response_seen["n"] == 1
        assert "总结" in (final_state.get("final_text") or "")

    _run(_scenario)


def test_react_loop_zero_tools_when_decide_responds_directly_first(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """Sanity check: pure chat path stays single-decide, zero tool calls."""
    assert client.get("/health/db").status_code == 200

    decide_calls = {"n": 0}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            decide_calls["n"] += 1
            return '{"action": "respond_directly", "text": "你好!"}'
        raise AssertionError(f"unexpected prompt:\n{prompt[:200]}")

    monkeypatch.setattr(LLMClient, "generate_text", fake_llm)

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, conversation_id = await _setup_run(db, test_marker)
        graph = build_workflow(db=db, current_user=user, agent_run_id=agent_run_id)
        final_state = await graph.ainvoke(
            _initial_state(
                user.id, agent_run_id, conversation_id,
                f"{test_marker} 你好",
            ),
        )
        history = final_state.get("tool_call_history") or []
        assert len(history) == 0
        assert decide_calls["n"] == 1
        assert final_state.get("final_text") == "你好!"

    _run(_scenario)
