"""ReadJobPostingTool 集成测试。"""

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.read_job_posting_tool import ReadJobPostingTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


_PARSED_JOB: dict[str, Any] = {
    "summary": "Build AI app",
    "responsibilities": ["设计 Agent 工作流"],
    "required_skills": ["Python"],
    "preferred_skills": [],
    "keywords": ["LLM"],
    "seniority": "中级",
    "city": "上海",
}


async def _setup(
    db: AsyncSession,
    *,
    marker: str,
    parsed: dict[str, Any] | None = _PARSED_JOB,
) -> tuple[User, int, int]:
    user = (await db.execute(select(User).where(User.username == "test"))).scalar_one()
    job = JobPosting(
        user_id=user.id,
        company_name=f"{marker} ReadCo",
        job_title="AI 应用研发工程师",
        city="上海",
        jd_text=f"{marker} JD 正文",
        parsed_json=parsed,
    )
    db.add(job)
    await db.flush()

    conversation = Conversation(user_id=user.id, title=f"{marker} read-job conv")
    db.add(conversation)
    await db.flush()
    agent_run = AgentRun(
        user_id=user.id,
        conversation_id=conversation.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(job)
    await db.refresh(agent_run)
    return user, agent_run.id, job.id


def _run(coro_factory) -> None:
    async def _do():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await coro_factory(db)
        finally:
            await engine.dispose()

    asyncio.run(_do())


async def _fetch_logs(db: AsyncSession, agent_run_id: int) -> list[ToolCallLog]:
    rows = await db.execute(
        select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
    )
    return list(rows.scalars().all())


def test_read_job_posting_tool_happy_path(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadJobPostingTool().invoke({"job_posting_id": job_id}, ctx)
        assert result["ok"] is True
        data = result["data"]
        assert data["id"] == job_id
        assert data["company_name"] == f"{test_marker} ReadCo"
        assert data["jd_text"] == f"{test_marker} JD 正文"
        assert data["parsed_json"]["seniority"] == "中级"
        assert data["parse_status"] == "parsed"

        logs = await _fetch_logs(db, agent_run_id)
        assert logs[0].status == "success"

    _run(_scenario)


def test_read_job_posting_tool_pending_job(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, job_id = await _setup(db, marker=test_marker, parsed=None)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadJobPostingTool().invoke({"job_posting_id": job_id}, ctx)
        assert result["ok"] is True
        assert result["data"]["parse_status"] == "pending"
        assert result["data"]["parsed_json"] is None

    _run(_scenario)


def test_read_job_posting_tool_not_found_returns_business_error(
    client: TestClient,
    test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id, _job_id = await _setup(db, marker=test_marker)
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ReadJobPostingTool().invoke({"job_posting_id": 999_999_999}, ctx)
        assert result["ok"] is False
        assert result["error_class"] == "job_posting_not_found"
        assert "list_user_jobs" in result["message_for_llm"]

    _run(_scenario)


def test_read_job_posting_tool_is_registered() -> None:
    from app.agent.tools import TOOL_REGISTRY

    assert TOOL_REGISTRY["read_job_posting"] is ReadJobPostingTool
