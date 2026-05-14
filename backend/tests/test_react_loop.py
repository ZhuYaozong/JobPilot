"""ReAct 多工具循环测试。

这里直接驱动 LangGraph workflow，不经过 HTTP 层。带状态的模拟 LLM 可以按脚本控制 decide 序列，
从而验证三类行为：

1. Agent 能在单轮对话里串联多个读取/动作工具。
2. ``tool_call_history`` 会按顺序累积条目。
3. 即使 decide 一直想继续调用工具，``MAX_TOOL_ITERATIONS`` (=3) 到达上限后也会强制进入 format_response。
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
    """第一次 decide 选择 list_user_jobs，第二次 decide 基于发现的岗位信息选择 respond_directly。

    同时验证工具调用会被记录到 tool_call_history。
    """
    assert client.get("/health/db").status_code == 200

    decide_calls = {"n": 0}

    # 提前放入一个岗位，确保 list_user_jobs 能返回数据。
    job_id_holder: dict[str, int] = {}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            decide_calls["n"] += 1
            if decide_calls["n"] == 1:
                # 第一次 decide：要求列出岗位。
                return (
                    '{"action": "call_tool", "tool": "list_user_jobs",'
                    f' "args": {{"query": "{test_marker}"}}}}'
                )
            # 后续 decide：LLM 已看到 list_user_jobs 结果，因此用友好的消息回复。
            assert "list_user_jobs" in prompt  # 历史区段。
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
        # 在当前用户下预置一个岗位，让 list_user_jobs 有内容可返回。
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

        # tool_call_history 应只有一条记录（list_user_jobs 调用），因为后续 decide 选择了 respond_directly。
        history = final_state.get("tool_call_history") or []
        assert len(history) == 1
        assert history[0]["tool"] == "list_user_jobs"
        assert history[0]["result"]["ok"] is True
        assert decide_calls["n"] == 2  # initial + follow-up

    _run(_scenario)


def test_react_loop_hits_max_iterations_and_forces_format_response(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """如果 decide 持续选择 call_tool，``MAX_TOOL_ITERATIONS`` 会在达到上限后强制 workflow 进入 format_response。

    同时验证 LLM 能看到最终回复 prompt，且工具历史已达到上限。
    """
    assert client.get("/health/db").status_code == 200

    decide_calls = {"n": 0}
    format_response_seen = {"n": 0}

    async def fake_llm(self, prompt: str) -> str:
        if "请严格按以下两种 JSON 之一回复" in prompt:
            decide_calls["n"] += 1
            # 始终选择 list_user_jobs，模拟 Agent 不主动停止的情况。
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

        # Workflow 正好执行 MAX_TOOL_ITERATIONS 次工具调用后，强制进入 format_response。
        history = final_state.get("tool_call_history") or []
        assert len(history) == MAX_TOOL_ITERATIONS
        assert final_state.get("iteration_count") == MAX_TOOL_ITERATIONS
        assert format_response_seen["n"] == 1
        assert "总结" in (final_state.get("final_text") or "")

    _run(_scenario)


def test_react_loop_zero_tools_when_decide_responds_directly_first(
    client: TestClient, monkeypatch, test_marker: str,
) -> None:
    """基础确认：纯聊天路径只执行一次 decide，且不调用工具。"""
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
