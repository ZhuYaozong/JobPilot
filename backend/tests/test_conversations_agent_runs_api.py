"""GET /api/v1/conversations/{id}/agent-runs 测试(任务 4 Agent 可观测)。"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


def _run(coro_factory: Callable) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


async def _seed_empty_conversation(db: AsyncSession, marker: str) -> int:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} empty-runs conv")
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation.id


async def _seed_conversation_with_runs(
    db: AsyncSession, marker: str,
) -> tuple[int, int, int]:
    """种一个会话 + 2 个 AgentRun;第二个 AgentRun 含 2 条 ToolCallLog。

    返回 (conversation_id, run1_id, run2_id),供测试断言用。
    """
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} agent-runs conv")
    db.add(conversation)
    await db.flush()

    base = datetime.now(timezone.utc) - timedelta(minutes=5)
    run1 = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="succeeded",
        started_at=base,
        finished_at=base + timedelta(seconds=2),
    )
    run2 = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="failed",
        error_class="llm_unavailable",
        error_detail=f"{marker} test llm unavailable",
        started_at=base + timedelta(minutes=1),
        finished_at=base + timedelta(minutes=1, seconds=3),
    )
    db.add_all([run1, run2])
    await db.flush()

    db.add_all([
        ToolCallLog(
            user_id=user.id,
            agent_run_id=run2.id,
            tool_name="list_user_jobs",
            status="success",
            arguments_json={"query": "腾讯"},
            result_json={"jobs": [], "count": 0},
            started_at=base + timedelta(minutes=1, seconds=0, microseconds=100),
            finished_at=base + timedelta(minutes=1, seconds=0, microseconds=500),
            latency_ms=400,
        ),
        ToolCallLog(
            user_id=user.id,
            agent_run_id=run2.id,
            tool_name="generate_cover_letter",
            status="failed",
            arguments_json={"resume_id": 1, "job_posting_id": 2},
            result_json=None,
            error_class="llm_unavailable",
            error_detail="upstream timeout",
            started_at=base + timedelta(minutes=1, seconds=1),
            finished_at=base + timedelta(minutes=1, seconds=2),
            latency_ms=1000,
        ),
    ])
    await db.commit()
    await db.refresh(conversation)
    await db.refresh(run1)
    await db.refresh(run2)
    return conversation.id, run1.id, run2.id


def test_list_agent_runs_empty_conversation(
    client: TestClient, test_marker: str,
) -> None:
    cid = _run(lambda db: _seed_empty_conversation(db, test_marker))
    resp = client.get(f"/api/v1/conversations/{cid}/agent-runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_agent_runs_with_tool_calls_nested(
    client: TestClient, test_marker: str,
) -> None:
    cid, run1_id, run2_id = _run(
        lambda db: _seed_conversation_with_runs(db, test_marker),
    )
    resp = client.get(f"/api/v1/conversations/{cid}/agent-runs")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 2

    # 按 started_at 升序:run1 在前。
    first, second = payload
    assert first["id"] == run1_id
    assert first["status"] == "succeeded"
    assert first["tool_calls"] == []

    assert second["id"] == run2_id
    assert second["status"] == "failed"
    assert second["error_class"] == "llm_unavailable"
    # 失败 run 的 error_detail 必须透出供前端展示。
    assert test_marker in second["error_detail"]

    tool_calls = second["tool_calls"]
    assert len(tool_calls) == 2
    # tool 调用按 started_at 升序:list_user_jobs 在前,generate_cover_letter 在后。
    assert tool_calls[0]["tool_name"] == "list_user_jobs"
    assert tool_calls[0]["status"] == "success"
    assert tool_calls[0]["arguments_json"] == {"query": "腾讯"}
    assert tool_calls[0]["result_json"] == {"jobs": [], "count": 0}
    assert tool_calls[0]["latency_ms"] == 400

    assert tool_calls[1]["tool_name"] == "generate_cover_letter"
    assert tool_calls[1]["status"] == "failed"
    assert tool_calls[1]["error_class"] == "llm_unavailable"
    assert tool_calls[1]["error_detail"] == "upstream timeout"
    assert tool_calls[1]["result_json"] is None


def test_list_agent_runs_returns_404_for_unknown_conversation(
    client: TestClient,
) -> None:
    resp = client.get("/api/v1/conversations/999999999/agent-runs")
    assert resp.status_code == 404


def test_list_agent_runs_user_scope_enforced(
    client: TestClient, test_marker: str,
) -> None:
    """跨用户的会话访问应当 404,不应当返回别人的 AgentRun。"""

    async def _seed_other_user_conv(db: AsyncSession) -> int:
        other = User(
            username=f"{test_marker}-other",
            display_name="Other User",
            is_test_user=True,
        )
        db.add(other)
        await db.flush()
        conv = Conversation(user_id=other.id, title=f"{test_marker} other conv")
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv.id

    other_cid = _run(_seed_other_user_conv)
    # client fixture 使用 X-User-Name=test,所以拿不到其他用户的会话。
    resp = client.get(f"/api/v1/conversations/{other_cid}/agent-runs")
    assert resp.status_code == 404
