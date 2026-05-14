"""三个读取工具的冒烟测试（list_user_jobs / list_user_resumes / list_user_applications）。

这些工具不会调用 LLM，也没有副作用，因此这里只验证：
  - 成功路径会返回当前用户自己的行；
  - 其他用户的行会被排除；
  - 可选过滤条件（query / current_stage）能正确收窄结果；
  - ToolCallLog 会以 status=success 记录。
"""

import asyncio
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_adapter import ToolContext
from app.agent.tools.list_user_applications_tool import ListUserApplicationsTool
from app.agent.tools.list_user_jobs_tool import ListUserJobsTool
from app.agent.tools.list_user_resumes_tool import ListUserResumesTool
from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.application_record import ApplicationRecord
from app.models.conversation import Conversation
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.tool_call_log import ToolCallLog
from app.models.user import User


def _run(coro_factory: Callable[[AsyncSession], Any]) -> Any:
    async def _do() -> Any:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await coro_factory(db)
        finally:
            await engine.dispose()

    return asyncio.run(_do())


async def _setup_agent_run(db: AsyncSession, marker: str) -> tuple[User, int]:
    user = (
        await db.execute(select(User).where(User.username == "test"))
    ).scalar_one()
    conversation = Conversation(user_id=user.id, title=f"{marker} read-tools conv")
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
    return user, agent_run.id


async def _other_user(db: AsyncSession) -> User:
    """解析 demo 用户，用于确认用户隔离逻辑。"""
    return (
        await db.execute(select(User).where(User.username == "demo"))
    ).scalar_one()


def test_list_user_jobs_returns_user_scoped_rows(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        other = await _other_user(db)

        db.add_all(
            [
                JobPosting(
                    user_id=user.id,
                    company_name=f"{test_marker} 腾讯",
                    job_title="后端工程师",
                    jd_text="...",
                ),
                JobPosting(
                    user_id=user.id,
                    company_name=f"{test_marker} 字节",
                    job_title="算法工程师",
                    jd_text="...",
                ),
                JobPosting(
                    user_id=other.id,
                    company_name=f"{test_marker} 阿里(other user)",
                    job_title="X",
                    jd_text="...",
                ),
            ],
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListUserJobsTool().invoke({}, ctx)
        assert result["ok"] is True

        companies = {job["company_name"] for job in result["data"]["jobs"]}
        # 两条带 test_marker 的记录属于当前用户；demo 用户拥有的记录不应出现。
        assert f"{test_marker} 腾讯" in companies
        assert f"{test_marker} 字节" in companies
        assert f"{test_marker} 阿里(other user)" not in companies

        log = (
            await db.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == agent_run_id),
            )
        ).scalar_one()
        assert log.status == "success"
        assert log.tool_name == "list_user_jobs"

    _run(_scenario)


def test_list_user_jobs_filters_by_query(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        db.add_all(
            [
                JobPosting(
                    user_id=user.id,
                    company_name=f"{test_marker} TencentQQ",
                    job_title="Backend",
                    jd_text="...",
                ),
                JobPosting(
                    user_id=user.id,
                    company_name=f"{test_marker} ByteDance",
                    job_title="ML",
                    jd_text="...",
                ),
            ],
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListUserJobsTool().invoke({"query": "Tencent"}, ctx)
        assert result["ok"] is True
        companies = {job["company_name"] for job in result["data"]["jobs"]}
        assert any("TencentQQ" in c for c in companies)
        assert not any("ByteDance" in c for c in companies)

    _run(_scenario)


def test_list_user_resumes_returns_user_scoped_rows(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        other = await _other_user(db)
        db.add_all(
            [
                Resume(
                    user_id=user.id,
                    title=f"{test_marker} mine",
                    raw_text="...",
                    content_hash=f"{test_marker}-rt-1",
                ),
                Resume(
                    user_id=other.id,
                    title=f"{test_marker} not mine",
                    raw_text="...",
                    content_hash=f"{test_marker}-rt-2",
                ),
            ],
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListUserResumesTool().invoke({}, ctx)
        titles = {r["title"] for r in result["data"]["resumes"]}
        assert f"{test_marker} mine" in titles
        assert f"{test_marker} not mine" not in titles

    _run(_scenario)


def test_list_user_applications_filters_by_stage(
    client: TestClient, test_marker: str,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        user, agent_run_id = await _setup_agent_run(db, test_marker)
        resume = Resume(
            user_id=user.id,
            title=f"{test_marker} app resume",
            raw_text="...",
            content_hash=f"{test_marker}-rt-app",
        )
        job = JobPosting(
            user_id=user.id,
            company_name=f"{test_marker} co",
            job_title="X",
            jd_text="...",
        )
        db.add_all([resume, job])
        await db.flush()
        db.add_all(
            [
                ApplicationRecord(
                    user_id=user.id,
                    resume_id=resume.id,
                    job_posting_id=job.id,
                    current_stage="applied",
                ),
                ApplicationRecord(
                    user_id=user.id,
                    resume_id=resume.id,
                    job_posting_id=job.id,
                    current_stage="interview",
                ),
            ],
        )
        await db.commit()

        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListUserApplicationsTool().invoke(
            {"current_stage": "interview"}, ctx,
        )
        stages = {a["current_stage"] for a in result["data"]["applications"]}
        assert "interview" in stages
        assert "applied" not in stages

    _run(_scenario)


def test_list_user_jobs_empty_when_no_rows(
    client: TestClient,
) -> None:
    assert client.get("/health/db").status_code == 200

    async def _scenario(db: AsyncSession) -> None:
        marker = "isolated-empty-jobs"
        user, agent_run_id = await _setup_agent_run(db, marker)
        # 使用一个不会匹配任何行的过滤条件。
        ctx = ToolContext(db=db, current_user=user, agent_run_id=agent_run_id)
        result = await ListUserJobsTool().invoke(
            {"query": "absolutely-nothing-matches-this"}, ctx,
        )
        assert result["ok"] is True
        assert result["data"]["jobs"] == []
        assert result["data"]["count"] == 0

    _run(_scenario)
